"""Paper models."""

from model.paper.paper_model import PaperModel
from model.paper.paper_content_model import PaperContentModel
from model.paper.paper_file_model import PaperFileModel
from model.paper.paper_source_meta_model import PaperSourceMetaModel

__all__ = [
    "PaperModel",
    "PaperContentModel",
    "PaperFileModel",
    "PaperSourceMetaModel",
]
