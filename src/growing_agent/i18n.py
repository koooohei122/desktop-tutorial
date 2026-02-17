from __future__ import annotations

SUPPORTED_LANGUAGES = ("en", "zh", "it", "fr", "pt", "hi", "ar", "ja", "es")
DEFAULT_LANGUAGE = "en"


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "run_completed": "Agent run completed.",
        "run_completed_with_errors": "Agent run finished with errors.",
        "status_loaded": "Loaded current state.",
        "state_reset": "State has been reset.",
        "language_updated": "Language preference updated.",
        "task_enqueued": "Autonomy task has been queued.",
        "challenges_spawned": "Challenge pack generated.",
        "autonomy_run_completed": "Autonomous work cycle completed.",
        "prompt_run_completed": "Prompt mission planned and executed.",
        "autonomy_status_loaded": "Loaded autonomous work status.",
        "desktop_windows_listed": "Window candidates listed.",
        "fun_status_loaded": "Loaded fun progression status.",
        "fun_level_up": "Level up! Great momentum.",
        "fun_new_badge": "New badge unlocked:",
        "fun_clean_run": "Clean run. Keep the streak going.",
        "fun_keep_going": "Nice try. Iterate and improve.",
        "fun_queue_empty": "Queue is empty. Spawn challenges to play.",
        "target_score_reached": "Stopped because target score was reached.",
        "command_error": "Stopped because command execution failed.",
    },
    "zh": {
        "run_completed": "智能代理运行已完成。",
        "run_completed_with_errors": "智能代理运行已完成，但存在错误。",
        "status_loaded": "已加载当前状态。",
        "state_reset": "状态已重置。",
        "language_updated": "语言偏好已更新。",
        "task_enqueued": "已将自主任务加入队列。",
        "autonomy_run_completed": "自主工作循环已完成。",
        "autonomy_status_loaded": "已加载自主工作状态。",
        "target_score_reached": "已达到目标分数，执行已停止。",
        "command_error": "由于命令执行失败，已停止。",
    },
    "it": {
        "run_completed": "Esecuzione dell'agente completata.",
        "run_completed_with_errors": "Esecuzione dell'agente completata con errori.",
        "status_loaded": "Stato corrente caricato.",
        "state_reset": "Lo stato e stato reimpostato.",
        "language_updated": "Preferenza lingua aggiornata.",
        "task_enqueued": "Attivita autonoma aggiunta alla coda.",
        "autonomy_run_completed": "Ciclo di lavoro autonomo completato.",
        "autonomy_status_loaded": "Stato del lavoro autonomo caricato.",
        "target_score_reached": "Interrotto per raggiungimento del punteggio obiettivo.",
        "command_error": "Interrotto per errore di esecuzione del comando.",
    },
    "fr": {
        "run_completed": "Execution de l'agent terminee.",
        "run_completed_with_errors": "Execution de l'agent terminee avec des erreurs.",
        "status_loaded": "Etat actuel charge.",
        "state_reset": "L'etat a ete reinitialise.",
        "language_updated": "La langue preferee a ete mise a jour.",
        "task_enqueued": "Tache autonome ajoutee a la file.",
        "autonomy_run_completed": "Cycle de travail autonome termine.",
        "autonomy_status_loaded": "Etat du travail autonome charge.",
        "target_score_reached": "Arret car le score cible a ete atteint.",
        "command_error": "Arret en raison d'un echec d'execution de commande.",
    },
    "pt": {
        "run_completed": "Execucao do agente concluida.",
        "run_completed_with_errors": "Execucao do agente concluida com erros.",
        "status_loaded": "Estado atual carregado.",
        "state_reset": "O estado foi redefinido.",
        "language_updated": "Preferencia de idioma atualizada.",
        "task_enqueued": "Tarefa autonoma adicionada a fila.",
        "autonomy_run_completed": "Ciclo de trabalho autonomo concluido.",
        "autonomy_status_loaded": "Estado do trabalho autonomo carregado.",
        "target_score_reached": "Parado porque a pontuacao alvo foi atingida.",
        "command_error": "Parado devido a falha na execucao do comando.",
    },
    "hi": {
        "run_completed": "एजेंट रन पूरा हुआ।",
        "run_completed_with_errors": "एजेंट रन पूरा हुआ, लेकिन त्रुटियां मिलीं।",
        "status_loaded": "वर्तमान स्थिति लोड की गई।",
        "state_reset": "स्थिति रीसेट कर दी गई है।",
        "language_updated": "भाषा वरीयता अपडेट की गई।",
        "task_enqueued": "स्वायत्त कार्य कतार में जोड़ा गया।",
        "autonomy_run_completed": "स्वायत्त कार्य चक्र पूरा हुआ।",
        "autonomy_status_loaded": "स्वायत्त कार्य स्थिति लोड की गई।",
        "target_score_reached": "लक्ष्य स्कोर प्राप्त होने के कारण रोका गया।",
        "command_error": "कमांड निष्पादन विफल होने के कारण रोका गया।",
    },
    "ar": {
        "run_completed": "اكتمل تشغيل الوكيل.",
        "run_completed_with_errors": "اكتمل تشغيل الوكيل مع وجود اخطاء.",
        "status_loaded": "تم تحميل الحالة الحالية.",
        "state_reset": "تمت اعادة تعيين الحالة.",
        "language_updated": "تم تحديث تفضيل اللغة.",
        "task_enqueued": "تمت اضافة مهمة مستقلة الى قائمة الانتظار.",
        "autonomy_run_completed": "اكتملت دورة العمل المستقل.",
        "autonomy_status_loaded": "تم تحميل حالة العمل المستقل.",
        "target_score_reached": "تم الايقاف لان درجة الهدف تحققت.",
        "command_error": "تم الايقاف بسبب فشل تنفيذ الامر.",
    },
    "ja": {
        "run_completed": "エージェント実行が完了しました。",
        "run_completed_with_errors": "エージェント実行は完了しましたが、エラーが発生しました。",
        "status_loaded": "現在の状態を読み込みました。",
        "state_reset": "状態を初期化しました。",
        "language_updated": "言語設定を更新しました。",
        "task_enqueued": "自律タスクをキューに追加しました。",
        "challenges_spawned": "チャレンジパックを生成しました。",
        "autonomy_run_completed": "自律作業サイクルが完了しました。",
        "prompt_run_completed": "プロンプトミッションを計画して実行しました。",
        "autonomy_status_loaded": "自律作業の状態を読み込みました。",
        "desktop_windows_listed": "ウィンドウ候補を一覧表示しました。",
        "fun_status_loaded": "ゲーム進行状況を読み込みました。",
        "fun_level_up": "レベルアップしました。最高です。",
        "fun_new_badge": "新しいバッジを獲得:",
        "fun_clean_run": "ノーミスで完了。連続記録を伸ばしましょう。",
        "fun_keep_going": "いい挑戦でした。次の一手で改善できます。",
        "fun_queue_empty": "キューが空です。チャレンジを生成して遊びましょう。",
        "target_score_reached": "目標スコアに到達したため停止しました。",
        "command_error": "コマンドエラーが発生したため停止しました。",
    },
    "es": {
        "run_completed": "La ejecucion del agente se completo.",
        "run_completed_with_errors": "La ejecucion del agente finalizo con errores.",
        "status_loaded": "Se cargo el estado actual.",
        "state_reset": "El estado ha sido reiniciado.",
        "language_updated": "Se actualizo la preferencia de idioma.",
        "task_enqueued": "La tarea autonoma se agrego a la cola.",
        "autonomy_run_completed": "Se completo el ciclo de trabajo autonomo.",
        "autonomy_status_loaded": "Se cargo el estado del trabajo autonomo.",
        "target_score_reached": "Se detuvo porque se alcanzo la puntuacion objetivo.",
        "command_error": "Se detuvo por fallo en la ejecucion del comando.",
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
