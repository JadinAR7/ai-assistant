# Trade Journal Smoke Test

Use this checklist before real-world Trade Journal import testing. It is manual coverage because the frontend currently has no test runner beyond lint/build.

## Preconditions

1. Backend is running.
2. Frontend is running.
3. Open `/trade-journal`.

## Import And Manual Mode

1. Confirm the page opens in `Import Trades` mode.
2. Confirm the manual entry form is not visible while `Import Trades` mode is active.
3. Click `Manual Entry`.
4. Confirm the manual entry form appears.
5. Click `Import Trades`.
6. Confirm the import upload section appears again.

## Import Review Completion

1. Upload a Performance PDF and optional Orders PDF.
2. Click `Preview Import`.
3. Confirm imported drafts appear as a step-based review queue.
4. Save or skip every draft.
5. Confirm the full PDF Import Preview collapses into the compact completion card.
6. Confirm the card says `Import complete` and shows the processed trade count.

## New Import Reset

1. From the compact completion card, click `New Import`.
2. Confirm selected PDF names are cleared.
3. Confirm draft statuses are cleared.
4. Confirm the active draft index resets by showing the upload/import section again.

## Journal Visibility

1. After completing an import, confirm saved trades remain visible in the Journal List View.
2. Select a saved imported trade.
3. Confirm Journal Detail View remains usable.
4. Click `View Journal` from the compact completion card if it is visible.
5. Confirm the import workflow is hidden/collapsed and the list/detail views remain visible.
