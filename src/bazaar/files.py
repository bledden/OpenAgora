"""File handling for AgentBazaar.

Supports uploading attachments to jobs (code files, images, documents)
and downloading job results in various formats.
"""

import os
import uuid
import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()

# File storage configuration
UPLOAD_DIR = Path(os.getenv("BAZAAR_UPLOAD_DIR", "/tmp/bazaar_uploads"))
MAX_FILE_SIZE_MB = int(os.getenv("BAZAAR_MAX_FILE_SIZE_MB", "50"))
MAX_FILES_PER_JOB = int(os.getenv("BAZAAR_MAX_FILES_PER_JOB", "10"))


class FileCategory(str, Enum):
    """Categories of uploadable files."""
    CODE = "code"
    IMAGE = "image"
    DOCUMENT = "document"
    DATA = "data"
    OTHER = "other"


# Allowed file extensions by category
ALLOWED_EXTENSIONS: dict[FileCategory, set[str]] = {
    FileCategory.CODE: {
        # Python
        ".py", ".pyi", ".pyx", ".pyd",
        # JavaScript/TypeScript
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        # Web
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        # Data formats
        ".json", ".yaml", ".yml", ".toml", ".xml",
        # Shell
        ".sh", ".bash", ".zsh", ".fish",
        # Other languages
        ".go", ".rs", ".java", ".kt", ".scala", ".c", ".cpp", ".h", ".hpp",
        ".cs", ".rb", ".php", ".swift", ".m", ".mm",
        # Config
        ".env", ".ini", ".cfg", ".conf",
        # Notebooks
        ".ipynb",
        # SQL
        ".sql",
        # Markdown/docs
        ".md", ".mdx", ".rst", ".txt",
    },
    FileCategory.IMAGE: {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    },
    FileCategory.DOCUMENT: {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".rtf",
    },
    FileCategory.DATA: {
        ".csv", ".tsv", ".parquet", ".arrow", ".feather",
        ".jsonl", ".ndjson",
    },
}

# Build reverse lookup: extension -> category
EXTENSION_TO_CATEGORY: dict[str, FileCategory] = {}
for category, extensions in ALLOWED_EXTENSIONS.items():
    for ext in extensions:
        EXTENSION_TO_CATEGORY[ext] = category


class JobAttachment(BaseModel):
    """Metadata for a file attached to a job."""
    file_id: str = Field(default_factory=lambda: f"file_{uuid.uuid4().hex[:12]}")
    job_id: str
    filename: str
    original_filename: str
    category: FileCategory
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    uploaded_by: str  # user_id or agent_id
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Storage path (relative to UPLOAD_DIR)
    storage_path: str


def get_file_category(filename: str) -> Optional[FileCategory]:
    """Determine file category from extension."""
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_CATEGORY.get(ext)


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return get_file_category(filename) is not None


def get_mime_type(filename: str) -> str:
    """Get MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def validate_file_size(size_bytes: int) -> bool:
    """Check if file size is within limits."""
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    return size_bytes <= max_bytes


def compute_checksum(content: bytes) -> str:
    """Compute SHA-256 checksum of file content."""
    return hashlib.sha256(content).hexdigest()


async def save_upload(
    job_id: str,
    filename: str,
    content: bytes,
    uploaded_by: str,
) -> JobAttachment:
    """Save an uploaded file and return attachment metadata.

    Args:
        job_id: Job this file is attached to
        filename: Original filename
        content: File content as bytes
        uploaded_by: User or agent ID who uploaded

    Returns:
        JobAttachment with file metadata

    Raises:
        ValueError: If file type not allowed or size exceeds limit
    """
    # Validate file type
    category = get_file_category(filename)
    if category is None:
        ext = Path(filename).suffix.lower()
        raise ValueError(f"File type '{ext}' is not allowed. Allowed types: code, images, documents, data files.")

    # Validate size
    if not validate_file_size(len(content)):
        raise ValueError(f"File size exceeds limit of {MAX_FILE_SIZE_MB}MB")

    # Generate storage path
    file_id = f"file_{uuid.uuid4().hex[:12]}"
    safe_filename = f"{file_id}_{Path(filename).name}"
    storage_path = f"{job_id}/{safe_filename}"

    # Ensure upload directory exists
    full_path = UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    full_path.write_bytes(content)

    # Compute checksum
    checksum = compute_checksum(content)

    # Create attachment record
    attachment = JobAttachment(
        file_id=file_id,
        job_id=job_id,
        filename=safe_filename,
        original_filename=filename,
        category=category,
        mime_type=get_mime_type(filename),
        size_bytes=len(content),
        checksum_sha256=checksum,
        uploaded_by=uploaded_by,
        storage_path=storage_path,
    )

    logger.info(
        "file_uploaded",
        file_id=file_id,
        job_id=job_id,
        category=category.value,
        size_bytes=len(content),
    )

    return attachment


async def get_file_path(attachment: JobAttachment) -> Optional[Path]:
    """Get the filesystem path for an attachment."""
    full_path = UPLOAD_DIR / attachment.storage_path
    if full_path.exists():
        return full_path
    return None


async def delete_file(attachment: JobAttachment) -> bool:
    """Delete an uploaded file."""
    full_path = UPLOAD_DIR / attachment.storage_path
    if full_path.exists():
        full_path.unlink()
        logger.info("file_deleted", file_id=attachment.file_id)
        return True
    return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# Export formats for job results
class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"


def export_result_as_json(result: dict) -> str:
    """Export job result as formatted JSON."""
    import json
    return json.dumps(result, indent=2, default=str)


def export_result_as_csv(result: dict) -> str:
    """Export job result as CSV (best effort for tabular data)."""
    import csv
    import io

    output = io.StringIO()

    # Try to find tabular data in result
    if isinstance(result, dict):
        # Check for common patterns
        if "data" in result and isinstance(result["data"], list):
            data = result["data"]
        elif "results" in result and isinstance(result["results"], list):
            data = result["results"]
        elif "items" in result and isinstance(result["items"], list):
            data = result["items"]
        else:
            # Flatten the dict itself
            data = [result]
    elif isinstance(result, list):
        data = result
    else:
        data = [{"result": str(result)}]

    if data and isinstance(data[0], dict):
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    else:
        writer = csv.writer(output)
        for item in data:
            writer.writerow([item])

    return output.getvalue()


def export_result_as_markdown(result: dict, job_title: str = "Job Result") -> str:
    """Export job result as Markdown."""
    import json

    lines = [
        f"# {job_title}",
        "",
        f"**Exported:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Result",
        "",
    ]

    if isinstance(result, dict):
        # Format as structured markdown
        for key, value in result.items():
            if isinstance(value, (dict, list)):
                lines.append(f"### {key}")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(value, indent=2, default=str))
                lines.append("```")
                lines.append("")
            else:
                lines.append(f"**{key}:** {value}")
                lines.append("")
    else:
        lines.append(str(result))

    return "\n".join(lines)


def export_result_as_text(result: dict) -> str:
    """Export job result as plain text."""
    import json

    if isinstance(result, dict):
        # Check for 'output' or 'text' field
        if "output" in result:
            return str(result["output"])
        if "text" in result:
            return str(result["text"])
        if "result" in result:
            return str(result["result"])

    return json.dumps(result, indent=2, default=str)
