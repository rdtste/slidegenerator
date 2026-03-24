"""QA Loop — orchestrates iterative quality assurance with Gemini Vision + programmatic fixes."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from app.config import settings
from app.services.gemini_vision_qa import SlideIssue, VisionQAResult, run_vision_qa
from app.services.pptx_fixer import FixResult, apply_fixes

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, Optional[int]], None]


class QALoopResult:
    """Final result of the QA loop."""

    def __init__(self):
        self.iterations_run: int = 0
        self.total_issues_found: int = 0
        self.total_fixes_applied: int = 0
        self.remaining_issues: list[SlideIssue] = []
        self.all_issues_history: list[dict] = []
        self.passed: bool = False
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "iterations_run": self.iterations_run,
            "total_issues_found": self.total_issues_found,
            "total_fixes_applied": self.total_fixes_applied,
            "remaining_errors": len([i for i in self.remaining_issues if i.severity == "error"]),
            "remaining_warnings": len([i for i in self.remaining_issues if i.severity == "warning"]),
            "passed": self.passed,
            "error": self.error,
            "issues": [i.to_dict() for i in self.remaining_issues[:10]],
        }


async def run_qa_loop(
    pptx_path: str,
    progress_callback: ProgressCallback | None = None,
    max_iterations: int | None = None,
) -> QALoopResult:
    """Run the full QA-Fix loop on a generated PPTX.

    Flow per iteration:
    1. Convert PPTX to images
    2. Analyze each slide with Gemini Vision
    3. If issues found: apply programmatic fixes
    4. Re-check only changed slides
    5. Repeat up to max_iterations

    Args:
        pptx_path: Path to the PPTX file to QA.
        progress_callback: Optional (step, message, progress) callback for SSE.
        max_iterations: Maximum fix iterations (default from config).

    Returns:
        QALoopResult with full QA history.
    """
    if max_iterations is None:
        max_iterations = settings.qa_max_iterations

    result = QALoopResult()
    slides_to_check: list[int] | None = None  # None = all slides

    def _progress(step: str, msg: str, pct: int | None = None):
        if progress_callback:
            progress_callback(step, msg, pct)

    for iteration in range(1, max_iterations + 1):
        result.iterations_run = iteration
        scope = "alle Folien" if slides_to_check is None else f"{len(slides_to_check)} Folie(n)"

        _progress(
            "qa_check",
            f"Qualitaetspruefung Runde {iteration}/{max_iterations} — {scope}...",
            None,
        )

        # Step 1: Vision QA
        try:
            qa_result: VisionQAResult = await run_vision_qa(
                pptx_path,
                slide_indices=slides_to_check,
                progress_callback=progress_callback,
            )
        except Exception as e:
            logger.error(f"[QA Loop] Vision QA failed in iteration {iteration}: {e}")
            result.error = f"Vision QA fehlgeschlagen: {str(e)[:100]}"
            # Don't fail the whole export — return what we have
            break

        if qa_result.error:
            logger.warning(f"[QA Loop] Vision QA error: {qa_result.error}")
            result.error = qa_result.error
            break

        issues = qa_result.issues
        result.total_issues_found += len(issues)

        # Record history
        for issue in issues:
            result.all_issues_history.append({
                "iteration": iteration,
                **issue.to_dict(),
            })

        error_count = len([i for i in issues if i.severity == "error"])
        warning_count = len([i for i in issues if i.severity == "warning"])

        logger.info(
            f"[QA Loop] Iteration {iteration}: "
            f"{error_count} errors, {warning_count} warnings"
        )

        # No issues? We're done
        if not issues:
            _progress("qa_pass", "Qualitaetspruefung bestanden!", None)
            result.passed = True
            break

        # Only fixable issues matter
        fixable = [i for i in issues if i.fix_action != "none"]

        if not fixable:
            # Issues found but nothing we can fix programmatically
            logger.info(
                f"[QA Loop] {len(issues)} issues found but none are auto-fixable"
            )
            result.remaining_issues = issues
            result.passed = error_count == 0  # Pass if only warnings
            _progress(
                "qa_done",
                f"Pruefung abgeschlossen — {warning_count} Hinweis(e)",
                None,
            )
            break

        # Step 2: Apply fixes
        fix_summary = ", ".join(
            sorted(set(i.fix_action for i in fixable))
        )
        _progress(
            "qa_fixing",
            f"Korrigiere {len(fixable)} Problem(e): {fix_summary}...",
            None,
        )

        try:
            fix_result: FixResult = apply_fixes(pptx_path, fixable)
        except Exception as e:
            logger.error(f"[QA Loop] Fix failed in iteration {iteration}: {e}")
            result.remaining_issues = issues
            break

        result.total_fixes_applied += len(fix_result.fixes_applied)

        if not fix_result.any_changes:
            # Fixes attempted but none worked
            result.remaining_issues = issues
            result.passed = error_count == 0
            break

        logger.info(
            f"[QA Loop] Applied {len(fix_result.fixes_applied)} fixes "
            f"on slides {fix_result.changed_slides}"
        )

        # Step 3: Set up re-check of only changed slides
        slides_to_check = fix_result.changed_slides

        # If last iteration, do final assessment
        if iteration == max_iterations:
            _progress(
                "qa_check",
                "Abschliessende Pruefung...",
                None,
            )
            try:
                final_qa = await run_vision_qa(
                    pptx_path,
                    slide_indices=slides_to_check,
                    progress_callback=progress_callback,
                )
                result.remaining_issues = final_qa.issues
                remaining_errors = len([i for i in final_qa.issues if i.severity == "error"])
                result.passed = remaining_errors == 0
            except Exception:
                result.remaining_issues = issues
                result.passed = error_count == 0

    # Final status message
    if result.passed:
        if result.total_fixes_applied > 0:
            _progress(
                "qa_pass",
                f"Qualitaetspruefung bestanden ({result.total_fixes_applied} Korrektur(en) angewendet)",
                None,
            )
        else:
            _progress("qa_pass", "Qualitaetspruefung bestanden!", None)
    else:
        remaining_errors = len([i for i in result.remaining_issues if i.severity == "error"])
        remaining_warnings = len([i for i in result.remaining_issues if i.severity == "warning"])
        _progress(
            "qa_done",
            f"Pruefung abgeschlossen — {remaining_errors} Problem(e), {remaining_warnings} Hinweis(e)",
            None,
        )

    logger.info(
        f"[QA Loop] Finished: {result.iterations_run} iterations, "
        f"{result.total_fixes_applied} fixes, passed={result.passed}"
    )

    return result
