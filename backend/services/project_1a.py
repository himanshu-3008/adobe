
"""
Adobe Hackathon Round 1A: PDF Structure Extraction
Extracts structured outlines (title and hierarchical headings) from PDF documents
"""

import json
import os
import sys
import re
import fitz  
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFStructureExtractor:
    def __init__(self):
    
        self.heading_patterns = [
            r'^(\d+\.?\s+)',
            r'^(\d+\.\d+\.?\s+)',  
            r'^(\d+\.\d+\.\d+\.?\s+)', 
            r'^([IVX]+\.?\s+)', 
            r'^([A-Z]\.?\s+)',  
            r'^([a-z]\.?\s+)',  
            r'^(Chapter\s+\d+)',  
            r'^(Section\s+\d+)',  
        ]


        self.title_indicators = [
            'title', 'heading', 'paper', 'article', 'study', 'research',
            'analysis', 'report', 'document', 'manuscript'
        ]

    def extract_structure(self, pdf_path: str) -> Dict:
        """Extract title and hierarchical outline from PDF"""
        try:
            doc = fitz.open(pdf_path)


            title = self._extract_title(doc)


            outline = self._extract_outline(doc)

            doc.close()

            return {
                "title": title,
                "outline": outline
            }

        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {
                "title": "Unknown Document",
                "outline": []
            }

    def _extract_title(self, doc: fitz.Document) -> str:
        """Extract document title using multiple strategies"""

    
        metadata_title = doc.metadata.get('title', '').strip()
        if metadata_title and len(metadata_title) > 3:
            return metadata_title


        if len(doc) > 0:
            page = doc[0]
            blocks = page.get_text("dict")["blocks"]

    
            title_candidates = []

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font_size = span["size"]
                            bbox = span["bbox"]

          
                            if bbox[1] < page.rect.height * 0.4 and len(text) > 5:
                                title_candidates.append((text, font_size, bbox[1]))

            if title_candidates:
            
                title_candidates.sort(key=lambda x: (-x[1], x[2]))


                potential_title = title_candidates[0][0]


                potential_title = re.sub(r'^[^a-zA-Z0-9]*', '', potential_title)
                potential_title = re.sub(r'[^a-zA-Z0-9]*$', '', potential_title)

                if len(potential_title) > 3:
                    return potential_title


        return "Unknown Document"

    def _extract_outline(self, doc: fitz.Document) -> List[Dict]:
        """Extract hierarchical outline from document"""
        outline = []


        toc = doc.get_toc()
        if toc:
            for item in toc[:50]: 
                level, title, page = item
                heading_level = f"H{min(level, 3)}"  
                outline.append({
                    "level": heading_level,
                    "text": title.strip(),
                    "page": page
                })

        
        if len(outline) < 3:
            outline = self._extract_headings_by_font_analysis(doc)

        return outline[:50] 

    def _extract_headings_by_font_analysis(self, doc: fitz.Document) -> List[Dict]:
        """Extract headings using font size and formatting analysis"""
        headings = []
        font_sizes = []
        all_text_blocks = []

      
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:
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

                        line_text = line_text.strip()
                        if line_text and len(line_text) > 2:
                            avg_font_size = sum(line_font_sizes) / len(line_font_sizes) if line_font_sizes else 0
                            is_bold = any(flag & 2**4 for flag in line_flags)  # Bold flag

                            all_text_blocks.append({
                                'text': line_text,
                                'font_size': avg_font_size,
                                'page': page_num + 1,
                                'is_bold': is_bold,
                                'bbox': line['bbox'] if 'bbox' in line else [0, 0, 0, 0]
                            })

                            font_sizes.append(avg_font_size)

        if not font_sizes:
            return []

  
        font_sizes.sort(reverse=True)
        base_font_size = Counter(font_sizes).most_common(1)[0][0]  

        h1_threshold = base_font_size * 1.4
        h2_threshold = base_font_size * 1.2
        h3_threshold = base_font_size * 1.1


        for block in all_text_blocks:
            text = block['text']
            font_size = block['font_size']
            page = block['page']
            is_bold = block['is_bold']


            if len(text) > 200:
                continue

            # Check if it matches heading patterns
            is_pattern_match = any(re.match(pattern, text) for pattern in self.heading_patterns)

            # Determine heading level
            heading_level = None

            if font_size >= h1_threshold or (is_bold and font_size >= base_font_size * 1.1):
                heading_level = "H1"
            elif font_size >= h2_threshold or (is_bold and is_pattern_match):
                heading_level = "H2"
            elif font_size >= h3_threshold or is_pattern_match:
                heading_level = "H3"

            if heading_level:
                # Clean up heading text
                clean_text = re.sub(r'^[^a-zA-Z0-9]*', '', text)
                clean_text = re.sub(r'[.]*$', '', clean_text).strip()

                if len(clean_text) > 2 and len(clean_text) < 150:
                    headings.append({
                        "level": heading_level,
                        "text": clean_text,
                        "page": page
                    })

        # Remove duplicates and sort by page
        seen = set()
        unique_headings = []
        for heading in headings:
            heading_key = (heading["text"].lower(), heading["page"])
            if heading_key not in seen:
                seen.add(heading_key)
                unique_headings.append(heading)

        unique_headings.sort(key=lambda x: x["page"])
        return unique_headings

def process_pdfs(input_dir: str, output_dir: str):
    """Process all PDFs in input directory"""
    extractor = PDFStructureExtractor()

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Process all PDF files
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            output_filename = filename.replace('.pdf', '.json')
            output_path = os.path.join(output_dir, output_filename)

            logger.info(f"Processing: {filename}")

            # Extract structure
            result = extractor.extract_structure(pdf_path)

            # Save result
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info(f"Completed: {filename} -> {output_filename}")

if __name__ == "__main__":
    input_directory = "/home/prit/Documents/pdfs"
    output_directory = "json_output"

    if not os.path.exists(input_directory):
        logger.error(f"Input directory {input_directory} does not exist")
        sys.exit(1)

    process_pdfs(input_directory, output_directory)
    logger.info("All PDFs processed successfully")
