"""
Tests T003 / SC003.

Given: three NEW papers where one PDF is broken.
When: download + process step is executed.
Then: broken paper is ERROR, others are DONE.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_model import PaperModel
from service.sync.pipeline_service import SyncPipelineService
from service.sync.types import PdfProcessResult
from tests.F001_auto_sync.helpers import FakeManifestProvider, FakeOaiProvider, FakePdfFetcher, FakePdfProcessor


@pytest.mark.asyncio
async def test_sc003_error_for_one_paper_does_not_stop_others(session: AsyncSession):
    papers = [
        PaperModel(source="arxiv", external_id="2401.10001", title="P1", categories="cond-mat.supr-con", status="NEW", payload={}),
        PaperModel(source="arxiv", external_id="2401.10002", title="P2", categories="cond-mat.supr-con", status="NEW", payload={}),
        PaperModel(source="arxiv", external_id="2401.10003", title="P3", categories="cond-mat.supr-con", status="NEW", payload={}),
    ]
    session.add_all(papers)
    await session.flush()

    ok_pdf_1 = b"pdf:ok-1"
    ok_pdf_2 = b"pdf:ok-2"
    broken_pdf = b"pdf:broken"

    processor = FakePdfProcessor(
        outputs={
            ok_pdf_1: PdfProcessResult(full_text="A", payload={"material": {}, "tc_K": None, "type": "", "dimensionality": "", "unconventional": False, "debye_frequency": []}, is_filtered=False),
            ok_pdf_2: PdfProcessResult(full_text="B", payload={"material": {}, "tc_K": None, "type": "", "dimensionality": "", "unconventional": False, "debye_frequency": []}, is_filtered=False),
        },
        error_payloads={broken_pdf},
    )
    fetcher = FakePdfFetcher(
        {
            "2401.10001": ok_pdf_1,
            "2401.10002": broken_pdf,
            "2401.10003": ok_pdf_2,
        }
    )
    service = SyncPipelineService(
        oai_provider=FakeOaiProvider([], checkpoint=None),
        manifest_provider=FakeManifestProvider(),
        pdf_fetcher=fetcher,
        pdf_processor=processor,
    )

    result = await service.run_download_and_process(session)

    assert result.processed_count == 3
    assert result.done_count == 2
    assert result.error_count == 1

    rows = list((await session.execute(select(PaperModel).order_by(PaperModel.external_id))).scalars().all())
    status_by_id = {row.external_id: row.status for row in rows}
    assert status_by_id["2401.10001"] == "DONE"
    assert status_by_id["2401.10003"] == "DONE"
    assert status_by_id["2401.10002"] == "ERROR"

    broken_row = next(row for row in rows if row.external_id == "2401.10002")
    assert broken_row.last_error is not None
    assert broken_row.attempts == 1

