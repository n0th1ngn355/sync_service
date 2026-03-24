"""
Tests T001 / SC001.

Given: OAI provider returns new records with mixed categories.
When: sync metadata step is executed.
Then: only cond-mat.supr-con records are inserted as NEW.
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_model import PaperModel
from model.sync.sync_state_model import SyncStateModel
from service.sync.pipeline_service import SyncPipelineService
from service.sync.types import OaiPaperRecord
from tests.F001_auto_sync.helpers import FakeManifestProvider, FakeOaiProvider, FakePdfFetcher, FakePdfProcessor


@pytest.mark.asyncio
async def test_sc001_sync_metadata_inserts_only_suprcon_records(session: AsyncSession):
    records = [
        OaiPaperRecord(
            external_id="2401.00001",
            title="A",
            categories="cond-mat.supr-con",
            datestamp=date(2026, 3, 20),
        ),
        OaiPaperRecord(
            external_id="2401.00002",
            title="B",
            categories="cond-mat.supr-con physics.chem-ph",
            datestamp=date(2026, 3, 20),
        ),
        OaiPaperRecord(
            external_id="2401.00003",
            title="C",
            categories="cond-mat.str-el",
            datestamp=date(2026, 3, 20),
        ),
        OaiPaperRecord(
            external_id="2401.00004",
            title="D",
            categories="hep-th",
            datestamp=date(2026, 3, 20),
        ),
        OaiPaperRecord(
            external_id="2401.00005",
            title="E",
            categories="cond-mat.supr-con",
            datestamp=date(2026, 3, 20),
        ),
    ]
    oai_provider = FakeOaiProvider(records, checkpoint=date(2026, 3, 20))
    service = SyncPipelineService(
        oai_provider=oai_provider,
        manifest_provider=FakeManifestProvider(),
        pdf_fetcher=FakePdfFetcher({}),
        pdf_processor=FakePdfProcessor({}),
    )

    result = await service.run_sync_metadata(session)

    assert result.inserted_count == 3
    assert result.checkpoint_datestamp == date(2026, 3, 20)

    papers = list((await session.execute(select(PaperModel).order_by(PaperModel.external_id))).scalars().all())
    assert len(papers) == 3
    assert {paper.external_id for paper in papers} == {"2401.00001", "2401.00002", "2401.00005"}
    assert all(paper.source == "arxiv" for paper in papers)
    assert all(paper.status == "NEW" for paper in papers)

    sync_state = (
        await session.execute(
            select(SyncStateModel).where(SyncStateModel.source == SyncPipelineService.SYNC_STATE_SOURCE_KEY)
        )
    ).scalar_one()
    assert sync_state.last_status == "OK"
    assert sync_state.last_success_datestamp == date(2026, 3, 20)
    assert oai_provider.calls == [None]

