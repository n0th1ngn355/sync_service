"""
Tests T002 / SC002.

Given: NEW paper with available PDF.
When: download + process step is executed.
Then: paper becomes DONE with content, payload and PDF/TXT file records.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_content_model import PaperContentModel
from model.paper.paper_file_model import PaperFileModel
from model.paper.paper_model import PaperModel
from service.sync.pipeline_service import SyncPipelineService
from service.sync.types import PdfProcessResult
from tests.F001_auto_sync.helpers import FakeManifestProvider, FakeOaiProvider, FakePdfFetcher, FakePdfProcessor


@pytest.mark.asyncio
async def test_sc002_download_and_process_marks_done_and_fills_content(session: AsyncSession):
    paper = PaperModel(
        source="arxiv",
        external_id="2311.05538",
        title="Test",
        categories="cond-mat.supr-con",
        status="NEW",
        payload={},
    )
    session.add(paper)
    await session.flush()
    await session.refresh(paper)

    pdf_payload = b"pdf:good"
    fake_processor = FakePdfProcessor(
        outputs={
            pdf_payload: PdfProcessResult(
                full_text="Superconducting material FeSe with Tc 35 K.",
                payload={
                    "material": {"FeSe": 2},
                    "tc_K": 35.0,
                    "type": "experiment",
                    "dimensionality": "2D",
                    "unconventional": False,
                    "debye_frequency": [],
                },
                is_filtered=False,
            )
        }
    )
    service = SyncPipelineService(
        oai_provider=FakeOaiProvider([], checkpoint=None),
        manifest_provider=FakeManifestProvider(mapping={"2311.05538": "arXiv_pdf_2311_001.tar"}),
        pdf_fetcher=FakePdfFetcher({"2311.05538": pdf_payload}),
        pdf_processor=fake_processor,
    )

    result = await service.run_download_and_process(session)

    assert result.processed_count == 1
    assert result.done_count == 1
    assert result.filtered_count == 0
    assert result.error_count == 0

    updated = (await session.execute(select(PaperModel).where(PaperModel.id == paper.id))).scalar_one()
    assert updated.status == "DONE"
    assert updated.payload["material"] == {"FeSe": 2}
    assert updated.payload["tc_K"] == 35.0
    assert updated.payload["type"] == "experiment"
    assert updated.payload["dimensionality"] == "2D"

    content = (await session.execute(select(PaperContentModel).where(PaperContentModel.paper_id == paper.id))).scalar_one()
    assert "FeSe" in content.full_text

    files = list((await session.execute(select(PaperFileModel).where(PaperFileModel.paper_id == paper.id))).scalars().all())
    file_types = {row.file_type for row in files}
    assert file_types == {"PDF", "TXT"}

