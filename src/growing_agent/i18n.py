from __future__ import annotations

SUPPORTED_LANGUAGES = ("ja", "en")
DEFAULT_LANGUAGE = "ja"


MESSAGES: dict[str, dict[str, str]] = {
    "ja": {
        "run_completed": "エージェント実行が完了しました。",
        "run_completed_with_errors": "エージェント実行は完了しましたが、エラーが発生しました。",
        "status_loaded": "現在の状態を読み込みました。",
        "state_reset": "状態を初期化しました。",
        "language_updated": "言語設定を更新しました。",
        "task_enqueued": "自律タスクをキューに追加しました。",
        "autonomy_run_completed": "自律作業サイクルが完了しました。",
        "autonomy_status_loaded": "自律作業の状態を読み込みました。",
        "target_score_reached": "目標スコアに到達したため停止しました。",
        "command_error": "コマンドエラーが発生したため停止しました。",
    },
    "en": {
        "run_completed": "Agent run completed.",
        "run_completed_with_errors": "Agent run finished with errors.",
        "status_loaded": "Loaded current state.",
        "state_reset": "State has been reset.",
        "language_updated": "Language preference updated.",
        "task_enqueued": "Autonomy task has been queued.",
        "autonomy_run_completed": "Autonomous work cycle completed.",
        "autonomy_status_loaded": "Loaded autonomous work status.",
        "target_score_reached": "Stopped because target score was reached.",
        "command_error": "Stopped because command execution failed.",
    },
}


def normalize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    normalized = language.strip().lower()
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return DEFAULT_LANGUAGE


def translate(key: str, language: str | None = None) -> str:
    lang = normalize_language(language)
    return (
        MESSAGES.get(lang, {}).get(key)
        or MESSAGES[DEFAULT_LANGUAGE].get(key)
        or key
    )
