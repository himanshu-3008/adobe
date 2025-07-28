# backend/api/views.py

import os
import json
import tempfile
import shutil
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

# Import your service classes
from services.project_1a import PDFStructureExtractor
from services.project_1b import DocumentIntelligenceAnalyzer

class DocumentAnalysisView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        service_type = request.data.get('service')
        files = request.FILES.getlist('files')

        if not service_type or not files:
            return Response({"error": "Service type and files are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a temporary directory to process files
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                if service_type == 'structure':
                    # --- Logic for Service 1A: Structure Extraction ---
                    if len(files) != 1:
                        return Response({"error": "Structure analysis requires exactly one PDF file."}, status=status.HTTP_400_BAD_REQUEST)

                    file_path = os.path.join(temp_dir, files[0].name)
                    with open(file_path, 'wb+') as f:
                        for chunk in files[0].chunks():
                            f.write(chunk)

                    extractor = PDFStructureExtractor()
                    result = extractor.extract_structure(file_path)
                    return Response(result, status=status.HTTP_200_OK)

                elif service_type == 'persona':
                    # --- Logic for Service 1B: Persona-Driven Analysis ---
                    persona = request.data.get('persona')
                    job_task = request.data.get('jobTask')

                    if not persona or not job_task:
                        return Response({"error": "Persona and Job Task are required for this service."}, status=status.HTTP_400_BAD_REQUEST)

                    # Save uploaded PDFs to the temp directory
                    doc_paths = []
                    doc_filenames = []
                    for f in files:
                        path = os.path.join(temp_dir, f.name)
                        with open(path, 'wb+') as temp_f:
                            for chunk in f.chunks():
                                temp_f.write(chunk)
                        doc_paths.append(path)
                        doc_filenames.append(f.name)

                    # Create the pdftosee.json config file
                    config = {
                        "persona": {"role": persona},
                        "job_to_be_done": {"task": job_task},
                        "documents": doc_filenames
                    }
                    config_path = os.path.join(temp_dir, "pdftosee.json")
                    with open(config_path, 'w') as f:
                        json.dump(config, f)

                    # Note: We call the class method directly, not the script's main function
                    analyzer = DocumentIntelligenceAnalyzer()
                    result = analyzer.analyze_documents(doc_paths, persona, job_task)
                    return Response(result, status=status.HTTP_200_OK)

                else:
                    return Response({"error": "Invalid service type specified."}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                # Log the exception e for debugging
                return Response({"error": f"An error occurred during processing: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)