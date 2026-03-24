"""
Tests T004 / SC004.

Given: DONE paper already exists.
When: download + process step is executed.
Then: DONE paper is skipped without updates.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_model import PaperModel
from service.sync.pipeline_service import SyncPipelineService
from tests.F001_auto_sync.helpers import FakeManifestProvider, FakeOaiProvider, FakePdfFetcher, FakePdfProcessor


@pytest.mark.asyncio
async def test_sc004_done_paper_is_not_reprocessed(session: AsyncSession):
    paper = PaperModel(
        source="arxiv",
        external_id="2401.20001",
        title="Already done",
        categories="cond-mat.supr-con",
        status="DONE",
        attempts=5,
        payload={"material": {"Nb3Sn": 1}},
    )
    session.add(paper)
    await session.flush()
    await session.refresh(paper)
    initial_updated_at = paper.updated_at

    service = SyncPipelineService(
        oai_provider=FakeOaiProvider([], checkpoint=None),
        manifest_provider=FakeManifestProvider(),
        pdf_fetcher=FakePdfFetcher({}),
        pdf_processor=FakePdfProcessor({}),
    )

    result = await service.run_download_and_process(session)

    assert result.processed_count == 0
    assert result.done_count == 0
    assert result.error_count == 0

    unchanged = (await session.execute(select(PaperModel).where(PaperModel.id == paper.id))).scalar_one()
    assert unchanged.status == "DONE"
    assert unchanged.attempts == 5
    assert unchanged.updated_at == initial_updated_at


@pytest.mark.asyncio
async def test_sc004_terminal_statuses_are_not_reprocessed(session: AsyncSession):
    terminal_statuses = ("COMPLETED", "FILTERED", "NOT_FOUND", "ERROR")
    papers: list[PaperModel] = []
    initial_timestamps: dict[int, object] = {}

    for idx, status in enumerate(terminal_statuses, start=1):
        paper = PaperModel(
            source="arxiv",
            external_id=f"2401.30{idx:03d}",
            title=f"Terminal {status}",
            categories="cond-mat.supr-con",
            status=status,
            attempts=3,
            payload={"material": {"Nb3Sn": 1}},
        )
        session.add(paper)
        papers.append(paper)

    await session.flush()
    for paper in papers:
        await session.refresh(paper)
        initial_timestamps[paper.id] = paper.updated_at

    service = SyncPipelineService(
        oai_provider=FakeOaiProvider([], checkpoint=None),
        manifest_provider=FakeManifestProvider(),
        pdf_fetcher=FakePdfFetcher({}),
        pdf_processor=FakePdfProcessor({}),
    )

    result = await service.run_download_and_process(session)
    assert result.processed_count == 0

    rows = list(
        (
            await session.execute(
                select(PaperModel).where(PaperModel.id.in_([paper.id for paper in papers]))
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        assert row.status in terminal_statuses
        assert row.updated_at == initial_timestamps[row.id]
