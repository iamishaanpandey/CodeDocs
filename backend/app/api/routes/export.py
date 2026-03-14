from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import io
import zipfile
from datetime import datetime
from fpdf import FPDF

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.documentation import Documentation

router = APIRouter()

@router.get("/{repo_id}/markdown")
async def export_repo_markdown(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Documentation).where(Documentation.repository_id == repo_id)
    docs = (await db.execute(stmt)).scalars().all()
    
    files = {}
    for doc in docs:
        if doc.file_path not in files:
            files[doc.file_path] = []
        files[doc.file_path].append(doc)
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path, funcs in files.items():
            md = f"# {file_path}\n\n## Functions\n\n"
            for func in funcs:
                if not func.function_name:
                    continue
                md += f"### {func.function_name}\n"
                md += f"**Lines of code:** {func.lines_of_code or 'Unknown'}\n"
                md += f"**Handles PII:** {'Yes' if func.handles_pii else 'No'}\n"
                md += f"**Is Entry Point:** {'Yes' if getattr(func, 'is_entry_point', False) else 'No'}\n\n"
                if func.docstring:
                    md += f"{func.docstring}\n\n"
                md += "---\n\n"
                
            safe_filename = file_path.replace("/", "_").replace("\\", "_") + ".md"
            zip_file.writestr(safe_filename, md)
            
    zip_buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=docs_{repo_id}.zip"}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

@router.get("/{repo_id}/pdf")
async def export_repo_pdf(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Documentation).where(Documentation.repository_id == repo_id)
    docs = (await db.execute(stmt)).scalars().all()
    
    files = {}
    total_funcs = 0
    for doc in docs:
        if doc.file_path not in files:
            files[doc.file_path] = []
        if doc.function_name:
            files[doc.file_path].append(doc)
            total_funcs += 1
            
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title Page
    pdf.add_page()
    pdf.set_font("helvetica", "B", 24)
    pdf.cell(0, 60, "Repository Documentation", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 16)
    pdf.cell(0, 10, f"Repository ID: {repo_id}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Total Functions: {total_funcs}", align="C", new_x="LMARGIN", new_y="NEXT")
    
    # TOC
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 15, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 12)
    for file_path in files.keys():
        pdf.cell(0, 10, f"- {file_path}", new_x="LMARGIN", new_y="NEXT")
        
    # Content
    for file_path, funcs in files.items():
        pdf.add_page()
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 15, f"File: {file_path}", new_x="LMARGIN", new_y="NEXT")
        
        for func in funcs:
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 10, f"{func.function_name}()", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "", 10)
            loc = func.lines_of_code or "Unknown"
            pii = "Yes" if func.handles_pii else "No"
            entry = "Yes" if getattr(func, 'is_entry_point', False) else "No"
            
            pdf.cell(0, 6, f"Lines of code: {loc} | Handles PII: {pii} | Entry Point: {entry}", new_x="LMARGIN", new_y="NEXT")
            if func.docstring:
                pdf.multi_cell(0, 5, func.docstring)
            pdf.cell(0, 5, "", new_x="LMARGIN", new_y="NEXT")
            
    pdf_buffer = io.BytesIO(pdf.output())
    pdf_buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=docs_{repo_id}.pdf"}
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
