# Changelog

> This file also contains basic usage notes for scripts in the project.

## Running OCR extraction script

From the workspace root execute one of the following commands to launch the
PDF‑to‑text conversion utility located at
`enterprise_project/scripts/extract_text_from_scanned_pdf.py`:

```powershell
cd enterprise_project
python scripts\extract_text_from_scanned_pdf.py
```

or, when treating the package as an importable module:

```powershell
cd enterprise_project
python -m enterprise_project.scripts.extract_text_from_scanned_pdf
```

Ensure that the appropriate Python environment is active and that
`easyocr`, `torch`, and other dependencies are installed. The script will
search for `.pdf` files under `static/files` relative to the project and
write corresponding `.txt` outputs.
