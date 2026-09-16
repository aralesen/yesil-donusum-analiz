# -*- coding: utf-8 -*-
"""
Yeşil Dönüşüm RAG (Retrieval-Augmented Generation) Motoru
PDF belgelerini okur, anlamsal parçalara böler ve FAISS vektör veritabanına kaydeder.
"""

import os
import faiss
import numpy as np
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

class GreenRAG:
    def __init__(self, folder_path="bilgi_havuzu", chunk_size=800, overlap=100):
        self.folder_path = folder_path
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks = []
        self.chunk_sources = [] # Hangi bilginin hangi PDF'ten geldiğini tutmak için
        
        # Türkçe'yi çok iyi anlayan, hızlı ve hafif çok dilli bir model kullanıyoruz
        print("🤖 Dil modeli yükleniyor... (İlk çalışmada 400MB kadar indirebilir, sonrasında anında açılır)")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
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
                
                # Metni üst üste binen (overlap) parçalara bölme işlemi
                words = text.split()
                for i in range(0, len(words), self.chunk_size - self.overlap):
                    chunk_text = " ".join(words[i:i + self.chunk_size])
                    if len(chunk_text.strip()) > 50: # Çok kısa işe yaramaz parçaları atla
                        self.chunks.append(chunk_text)
                        self.chunk_sources.append(file)
            except Exception as e:
                print(f"❌ {file} okunurken hata oluştu: {e}")

        print(f"✅ Toplam {len(self.chunks)} adet anlamlı metin parçası (chunk) oluşturuldu.")
        return True

    def build_vector_db(self):
        """Oluşturulan metin parçalarını vektörlere çevirip FAISS indeksine kaydeder."""
        if not self.chunks:
            print("⚠️ Vektörleştirilecek metin bulunamadı. Önce PDF'leri okutmalısınız.")
            return

        print("🧠 Metinler yapay zeka tarafından matematiksel vektörlere çevriliyor... Lütfen bekleyin.")
        # Metinleri embedding (koordinat) formatına çevir
        embeddings = self.model.encode(self.chunks, convert_to_numpy=True)
        
        # FAISS vektör veritabanını oluştur (L2 Mesafe / Öklid uzaklığı kullanır)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        print(f"✅ Vektör veritabanı hazır! FAISS indeksine {self.index.ntotal} kayıt eklendi.")

    def search(self, query, top_k=3):
        """Kullanıcının sorusuna semantik olarak en yakın paragrafları bulur."""
        if not self.index:
            return "Veritabanı henüz oluşturulmadı."
            
        # Kullanıcının sorusunu da aynı uzayda vektöre çevir
        query_vector = self.model.encode([query], convert_to_numpy=True)
        
        # En yakın (en benzer) K adet sonucu FAISS içinde ara
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for i in range(top_k):
            idx = indices[0][i]
            if idx != -1 and idx < len(self.chunks):
                results.append({
                    "source": self.chunk_sources[idx],
                    "text": self.chunks[idx],
                    "distance": distances[0][i] # Mesafe ne kadar küçükse o kadar benzer
                })
        return results

# Bu dosya tek başına çalıştırıldığında test amaçlı aşağıdaki blok devreye girer
if __name__ == "__main__":
    print("--- RAG SİSTEMİ TEST BAŞLATILIYOR ---")
    rag = GreenRAG()
    
    # 1. Klasördeki PDF'leri oku
    is_loaded = rag.read_and_chunk_pdfs()
    
    if is_loaded:
        # 2. FAISS Vektör DB oluştur
        rag.build_vector_db()
        
        # 3. Test araması yap
        test_sorusu = "Karbon vergisi veya SKDM uyumu için ne yapmalıyım?"
        print(f"\n🔎 TEST SORUSU: '{test_sorusu}'")
        sonuclar = rag.search(test_sorusu, top_k=2)
        
        print("\n🎯 EN İYİ EŞLEŞEN SONUÇLAR:")
        for no, sonuc in enumerate(sonuclar, 1):
            print(f"\n--- Sonuç {no} (Kaynak: {sonuc['source']}) ---")
            print(sonuc['text'][:400] + "...") # Çok uzun olmasın diye ilk 400 karakteri yazdır