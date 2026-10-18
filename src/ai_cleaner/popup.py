"""Small standard-library tkinter approval popup."""

from __future__ import annotations

from typing import Any

from ai_cleaner.domain.actions import RecoveryActionPlan
from ai_cleaner.domain.proposals import Proposal
from ai_cleaner.terminal import CleanupDecision, RecoveryDecision


class PopupInteraction:
    """Human review adapter. Failure to display always retains every file."""

    def __init__(self) -> None:
        self._available: bool | None = None

    @property
    def interactive(self) -> bool:
        if self._available is None:
            self._available = self._probe()
        return self._available

    def _probe(self) -> bool:
        try:
            tk, _ttk, _messagebox = self._modules()
            root = tk.Tk()
            root.withdraw()
            root.update_idletasks()
            root.destroy()
        except Exception:
            # Any popup creation failure must fail closed without minting approval.
            return False
        return True

    @staticmethod
    def _modules() -> tuple[Any, Any, Any]:
        import tkinter as tk
        from tkinter import messagebox, ttk

        return tk, ttk, messagebox

    def choose_cleanup(self, proposal: Proposal) -> CleanupDecision:
        if not self.interactive:
            return CleanupDecision(frozenset(), frozenset(), True)
        try:
            return self._choose_cleanup_window(proposal)
        except Exception:
            self._available = False
            return CleanupDecision(frozenset(), frozenset(), True)

    def show_nothing_eligible(self) -> None:
        if not self.interactive:
            return
        try:
            tk, _ttk, messagebox = self._modules()
            root = tk.Tk()
            root.withdraw()
            try:
                messagebox.showinfo(
                    "AI-cleaner",
                    "Nothing eligible for cleanup. All project files were retained.",
                    parent=root,
                )
            finally:
                root.destroy()
        except Exception:
            self._available = False

    def _choose_cleanup_window(self, proposal: Proposal) -> CleanupDecision:
        tk, ttk, _messagebox = self._modules()
        root = tk.Tk()
        root.title("AI-cleaner review")
        root.geometry("760x520")
        result = CleanupDecision(frozenset(), frozenset(), True)
        variables: list[tuple[str, Any, int]] = []

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text=(
                f"Project: {proposal.root}\n"
                f"Task: {proposal.task_label or proposal.task_id or 'untracked'}"
            ),
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Choose only disposable files. Quarantine is recoverable and does not reclaim "
                "disk space. All files start unchecked."
            ),
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(6, 8))

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        rows = ttk.Frame(canvas)
        rows.bind(
            "<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        summary = tk.StringVar(value="0 files selected · 0 bytes")

        def update_summary() -> None:
            chosen = [(path, size) for path, variable, size in variables if variable.get()]
            summary.set(f"{len(chosen)} files selected · {sum(size for _, size in chosen)} bytes")

        for item in proposal.items:
            variable = tk.BooleanVar(value=False)
            variables.append((item.relative_path, variable, item.size))
            ttk.Checkbutton(
                rows,
                variable=variable,
                command=update_summary,
                text=f"{item.relative_path}  ({item.size} bytes)\n{item.explanation}",
            ).pack(anchor="w", fill="x", pady=4)

        def finish(*, protect: bool = False, cancel: bool = False) -> None:
            nonlocal result
            chosen = frozenset(path for path, variable, _size in variables if variable.get())
            result = CleanupDecision(
                frozenset() if protect else chosen,
                chosen if protect else frozenset(),
                cancel,
            )
            root.destroy()

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0), side="bottom")
        ttk.Label(footer, textvariable=summary).pack(side="left")
        ttk.Button(footer, text="Cancel", command=lambda: finish(cancel=True)).pack(side="right")
        ttk.Button(
            footer, text="Move selected to quarantine", command=lambda: finish()
        ).pack(side="right", padx=6)
        ttk.Button(
            footer, text="Keep selected", command=lambda: finish(protect=True)
        ).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", lambda: finish(cancel=True))
        root.mainloop()
        return result

    def choose_recovery(self, plan: RecoveryActionPlan) -> RecoveryDecision:
        if not self.interactive:
            return RecoveryDecision(frozenset(), True)
        try:
            return self._choose_recovery_window(plan)
        except Exception:
            self._available = False
            return RecoveryDecision(frozenset(), True)

    def _choose_recovery_window(self, plan: RecoveryActionPlan) -> RecoveryDecision:
        tk, ttk, _messagebox = self._modules()
        root = tk.Tk()
        root.title(f"AI-cleaner {plan.action}")
        root.geometry("720x440")
        result = RecoveryDecision(frozenset(), True)
        variables: list[tuple[str, Any]] = []
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        warning = (
            "Permanent purge cannot be undone."
            if plan.action == "purge"
            else "Restore never overwrites an existing destination."
        )
        ttk.Label(frame, text=warning).pack(anchor="w", pady=(0, 8))
        for item in plan.items:
            variable = tk.BooleanVar(value=False)
            variables.append((item.recovery_id, variable))
            ttk.Checkbutton(
                frame,
                variable=variable,
                text=f"{item.source}\n→ {item.destination}  ({item.size} bytes)",
            ).pack(anchor="w", fill="x", pady=4)

        def finish(*, cancel: bool = False) -> None:
            nonlocal result
            selected = frozenset(key for key, variable in variables if variable.get())
            result = RecoveryDecision(selected, cancel)
            root.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=lambda: finish(cancel=True)).pack(side="right")
        ttk.Button(buttons, text=f"Continue with {plan.action}", command=finish).pack(
            side="right", padx=6
        )
        root.protocol("WM_DELETE_WINDOW", lambda: finish(cancel=True))
        root.mainloop()
        return result

    def confirm_exact(self, action: str, digest: str, summary: tuple[str, ...]) -> bool:
        if not self.interactive:
            return False
        try:
            tk, _ttk, messagebox = self._modules()
            root = tk.Tk()
            root.withdraw()
            try:
                return bool(
                    messagebox.askokcancel(
                        "Confirm exact AI-cleaner operation",
                        "\n".join((*summary, f"Proposal digest: {digest}")),
                        icon="warning",
                        default="cancel",
                        parent=root,
                    )
                )
            finally:
                root.destroy()
        except Exception:
            self._available = False
            return False
