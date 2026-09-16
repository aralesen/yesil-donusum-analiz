# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm RAG (Retrieval-Augmented Generation) Motoru
Cross-Encoder Reranker entegrasyonu ile hassaslaştırılmış semantik arama modülü.
"""

import os
import faiss
import numpy as np
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder

class GreenRAG:
    def __init__(self, folder_path="bilgi_havuzu", chunk_size=800, overlap=100):
        self.folder_path = folder_path
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks = []
        self.chunk_sources = []
        
        # 1. Aşama Modeli: Metinleri hızlıca vektörlere (koordinatlara) çeviren model
        print("🤖 Vektör (Embedding) modeli yükleniyor...")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # 2. Aşama Modeli: Bulunan sonuçların mantıksal doğrulamasını yapan Reranker (Yeniden Sıralayıcı)
        print("🧠 Reranker (Mantıksal Süzgeç) modeli yükleniyor...")
        # Çok dilli (Türkçe dahil) hassas yeniden sıralama modeli
        self.reranker = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')
        
        self.index = None

    def read_and_chunk_pdfs(self):
        """Klasördeki PDF'leri okur ve belirlenen boyutlarda parçalara (chunk) böler."""
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
            print(f"⚠️ '{self.folder_path}' klasörü bulunamadı, yeni oluşturuldu. Lütfen içine PDF ekleyin.")
            return False

        pdf_files = [f for f in os.listdir(self.folder_path) if f.endswith('.pdf')]
        
        if not pdf_files:
            print(f"⚠️ '{self.folder_path}' klasöründe PDF bulunamadı.")
            return False

        print(f"📚 {len(pdf_files)} adet PDF bulundu. Okunuyor ve parçalanıyor...")
        
        for file in pdf_files:
            file_path = os.path.join(self.folder_path, file)
            try:
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                
                words = text.split()
                for i in range(0, len(words), self.chunk_size - self.overlap):
                    chunk_text = " ".join(words[i:i + self.chunk_size])
                    if len(chunk_text.strip()) > 50:
                        self.chunks.append(chunk_text)
                        self.chunk_sources.append(file)
            except Exception as e:
                print(f"❌ {file} okunurken hata oluştu: {e}")

        print(f"✅ Toplam {len(self.chunks)} adet anlamlı metin parçası (chunk) oluşturuldu.")
        return True

    def build_vector_db(self):
        """Oluşturulan metin parçalarını vektörlere çevirip FAISS indeksine kaydeder."""
        if not self.chunks:
            print("⚠️ Vektörleştirilecek metin bulunamadı.")
            return

        print("🧠 Metinler yapay zeka tarafından matematiksel vektörlere çevriliyor...")
        embeddings = self.model.encode(self.chunks, convert_to_numpy=True)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        print(f"✅ Vektör veritabanı hazır! FAISS indeksine {self.index.ntotal} kayıt eklendi.")

    def search(self, query, top_k=2, fetch_k=10):
        """
        İki aşamalı hibrit arama:
        1. FAISS ile en yakın 'fetch_k' (10) adayı bul.
        2. Cross-Encoder ile bu adayları okuyup mantık puanı ver, en iyi 'top_k' (2) adayı döndür.
        """
        if self.index is None or self.index.ntotal == 0 or not str(query).strip():
            return []

        # --- AŞAMA 1: FAISS Kaba Arama ---
        fetch_k = min(fetch_k, self.index.ntotal)
        query_vector = self.model.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(query_vector, fetch_k)
        
        initial_results = []
        for i in range(fetch_k):
            idx = indices[0][i]
            if idx != -1 and idx < len(self.chunks):
                initial_results.append({
                    "source": self.chunk_sources[idx],
                    "text": self.chunks[idx],
                    "faiss_distance": distances[0][i]
                })
                
        if not initial_results:
            return []

        # --- AŞAMA 2: Cross-Encoder Hassas Yeniden Sıralama ---
        # Soru ile her bir paragrafı çift (pair) haline getirip Reranker'a veriyoruz
        pairs = [[query, res["text"]] for res in initial_results]
        cross_scores = self.reranker.predict(pairs)
        
        # Yapay zekanın verdiği mantık puanlarını (skorları) sonuçlara ekle
        for i, score in enumerate(cross_scores):
            initial_results[i]["cross_score"] = float(score)
            
        # Puanlara göre büyükten küçüğe sırala (En alakalı olan en üste çıkar)
        initial_results.sort(key=lambda x: x["cross_score"], reverse=True)
        
        # Sadece en iyi top_k (örn: 2) sonucu döndür
        return initial_results[:top_k]

# Test Bloğu
if __name__ == "__main__":
    print("--- RAG RERANKER TEST BAŞLATILIYOR ---")
    rag = GreenRAG()
    
    if rag.read_and_chunk_pdfs():
        rag.build_vector_db()
        
        test_sorusu = "Karbon vergisi veya SKDM uyumu için ne yapmalıyım?"
        print(f"\n🔎 TEST SORUSU: '{test_sorusu}'")
        sonuclar = rag.search(test_sorusu, top_k=2)
        
        print("\n🎯 EN İYİ EŞLEŞEN SONUÇLAR (RERANKED):")
        for no, sonuc in enumerate(sonuclar, 1):
            print(f"\n--- Sonuç {no} (Kaynak: {sonuc['source']} | Alaka Puanı: {sonuc['cross_score']:.2f}) ---")
            print(sonuc['text'][:400] + "...")
