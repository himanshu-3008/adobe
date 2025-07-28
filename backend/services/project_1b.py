#!/usr/bin/env python3
"""
Adobe Hackathon Round 1B: Persona-Driven Document Intelligence
Extracts and prioritizes relevant sections from document collections based on specific personas
"""

import json
import os
import sys
import re
import fitz  # PyMuPDF
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentIntelligenceAnalyzer:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95
        )
        self.lsa = TruncatedSVD(n_components=100, random_state=42)

    def analyze_documents(self, documents: List[str], persona: str, job_to_be_done: str) -> Dict:
        """Analyze documents based on persona and job requirements"""
        try:
            # Extract sections from all documents
            all_sections = self._extract_all_sections(documents)

            if not all_sections:
                return self._empty_result(documents, persona, job_to_be_done)

            # Create persona-job query for relevance scoring
            query_text = f"{persona} {job_to_be_done}"

            # Score and rank sections
            ranked_sections = self._score_sections(all_sections, query_text)

            # Generate sub-section analysis
            subsections = self._generate_subsections(ranked_sections[:20], query_text)

            return {
                "metadata": {
                    "input_documents": documents,
                    "persona": persona,
                    "job_to_be_done": job_to_be_done,
                    "processing_timestamp": datetime.now().isoformat()
                },
                "extracted_sections": ranked_sections[:15],  # Top 15 sections
                "subsection_analysis": subsections[:10]  # Top 10 subsections
            }

        except Exception as e:
            logger.error(f"Error in document analysis: {str(e)}")
            return self._empty_result(documents, persona, job_to_be_done)

    def _extract_all_sections(self, documents: List[str]) -> List[Dict]:
        """Extract sections from all documents"""
        all_sections = []

        for doc_path in documents:
            if not os.path.exists(doc_path):
                logger.warning(f"Document not found: {doc_path}")
                continue

            try:
                doc = fitz.open(doc_path)
                doc_name = os.path.basename(doc_path)

                sections = self._extract_sections_from_document(doc, doc_name)
                all_sections.extend(sections)

                doc.close()

            except Exception as e:
                logger.error(f"Error processing {doc_path}: {str(e)}")

        return all_sections

    def _extract_sections_from_document(self, doc: fitz.Document, doc_name: str) -> List[Dict]:
        """Extract sections from a single document"""
        sections = []
        current_section = {"title": "", "content": "", "page": 1}

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:
                    block_text = ""
                    is_heading = False
                    font_sizes = []

                    for line in block["lines"]:
                        line_text = ""
                        line_font_sizes = []
                        line_flags = []

                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:
                                line_text += text + " "
                                line_font_sizes.append(span["size"])
                                line_flags.append(span["flags"])

                        if line_text.strip():
                            block_text += line_text + "\n"
                            font_sizes.extend(line_font_sizes)

                    block_text = block_text.strip()

                    if block_text:
                        # Determine if this is a heading
                        avg_font_size = np.mean(font_sizes) if font_sizes else 12
                        is_bold = any(flag & 2**4 for flag in line_flags)
                        is_short = len(block_text) < 100
                        has_heading_pattern = bool(re.match(r'^(\d+\.?\s+|Chapter|Section|Introduction|Conclusion|Abstract|References)', block_text, re.IGNORECASE))

                        is_heading = (is_bold and is_short) or has_heading_pattern or avg_font_size > 14

                        if is_heading and current_section["content"].strip():
                            # Save previous section
                            if len(current_section["content"].strip()) > 50:
                                sections.append({
                                    "document": doc_name,
                                    "page_number": current_section["page"],
                                    "section_title": current_section["title"] or "Untitled Section",
                                    "content": current_section["content"].strip()
                                })

                            # Start new section
                            current_section = {
                                "title": block_text[:100],  # Limit title length
                                "content": "",
                                "page": page_num + 1
                            }
                        else:
                            if is_heading and not current_section["title"]:
                                current_section["title"] = block_text[:100]
                                current_section["page"] = page_num + 1
                            else:
                                current_section["content"] += block_text + "\n\n"

        # Add final section
        if current_section["content"].strip() and len(current_section["content"].strip()) > 50:
            sections.append({
                "document": doc_name,
                "page_number": current_section["page"],
                "section_title": current_section["title"] or "Untitled Section",
                "content": current_section["content"].strip()
            })

        return sections

    def _score_sections(self, sections: List[Dict], query: str) -> List[Dict]:
        """Score and rank sections based on relevance to persona and job"""
        if not sections:
            return []

        # Prepare texts for vectorization
        section_texts = [f"{section['section_title']} {section['content']}" for section in sections]
        all_texts = section_texts + [query]

        try:
            # Vectorize texts
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)

            # Apply LSA for dimensionality reduction
            lsa_matrix = self.lsa.fit_transform(tfidf_matrix)

            # Query vector is the last one
            query_vector = lsa_matrix[-1:, :]
            section_vectors = lsa_matrix[:-1, :]

            # Calculate similarity scores
            similarities = cosine_similarity(query_vector, section_vectors)[0]

            # Add scores to sections
            scored_sections = []
            for i, section in enumerate(sections):
                section_copy = section.copy()
                section_copy["importance_rank"] = float(similarities[i])
                scored_sections.append(section_copy)

            # Sort by importance score
            scored_sections.sort(key=lambda x: x["importance_rank"], reverse=True)

            # Assign rank numbers
            for i, section in enumerate(scored_sections):
                section["importance_rank"] = i + 1

            return scored_sections

        except Exception as e:
            logger.error(f"Error in section scoring: {str(e)}")
            # Return sections with default ranking
            for i, section in enumerate(sections):
                section["importance_rank"] = i + 1
            return sections

    def _generate_subsections(self, top_sections: List[Dict], query: str) -> List[Dict]:
        """Generate refined subsection analysis"""
        subsections = []

        for section in top_sections[:10]:  # Process top 10 sections
            content = section["content"]

            # Split content into paragraphs
            paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 100]

            if not paragraphs:
                paragraphs = [content[:500]]  # Use first 500 chars if no good paragraphs

            # Score paragraphs
            try:
                paragraph_texts = paragraphs + [query]
                tfidf_matrix = self.vectorizer.transform(paragraph_texts)
                lsa_matrix = self.lsa.transform(tfidf_matrix)

                query_vector = lsa_matrix[-1:, :]
                paragraph_vectors = lsa_matrix[:-1, :]

                similarities = cosine_similarity(query_vector, paragraph_vectors)[0]

                # Select best paragraph
                best_idx = np.argmax(similarities)
                refined_text = paragraphs[best_idx][:300] + "..." if len(paragraphs[best_idx]) > 300 else paragraphs[best_idx]

                subsections.append({
                    "document": section["document"],
                    "section_title": section["section_title"],
                    "refined_text": refined_text,
                    "page_number": section["page_number"]
                })

            except Exception as e:
                logger.error(f"Error processing subsection: {str(e)}")
                # Fallback: use first paragraph
                refined_text = paragraphs[0][:300] + "..." if len(paragraphs[0]) > 300 else paragraphs[0]
                subsections.append({
                    "document": section["document"],
                    "section_title": section["section_title"],
                    "refined_text": refined_text,
                    "page_number": section["page_number"]
                })

        return subsections

    def _empty_result(self, documents: List[str], persona: str, job_to_be_done: str) -> Dict:
        """Return empty result structure"""
        return {
            "metadata": {
                "input_documents": documents,
                "persona": persona,
                "job_to_be_done": job_to_be_done,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": [],
            "subsection_analysis": []
        }

def process_document_analysis(input_dir: str, output_dir: str):
    """Process document analysis based on configuration"""

    # Load configuration
    config_path = os.path.join(input_dir, "pdftosee.json")
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)
    persona = config.get("persona", {}).get("role", "")
    job_to_be_done = config.get("job_to_be_done", {}).get("task", "")

    # Convert relative paths to absolute paths
    documents_info = config.get("documents", [])
    document_paths = []

    for item in documents_info:
        if isinstance(item, dict):
            filename = item.get("filename")
        else:
            filename = item
        if filename:
            document_paths.append(os.path.join(input_dir, filename))

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Initialize analyzer
    analyzer = DocumentIntelligenceAnalyzer()

    logger.info(f"Processing {len(document_paths)} documents for persona: {persona}")

    # Analyze documents
    result = analyzer.analyze_documents(document_paths, persona, job_to_be_done)

    # Save result
    output_path = os.path.join(output_dir, "analysis_result.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Analysis completed. Results saved to: analysis_result.json")

if __name__ == "__main__":
    input_directory = "/home/prit/Documents/pdf2"
    output_directory = "/home/prit/Documents/json_output2"

    if not os.path.exists(input_directory):
        logger.error(f"Input directory {input_directory} does not exist")
        sys.exit(1)

    process_document_analysis(input_directory, output_directory)
    logger.info("Document analysis completed successfully")
