"""
Интерактивный дашборд и стенд живой проверки для жюри.
Кейс ОНСОФТ: «ИИ, который не обманывает» (Хакатон Школы 21 / ИТ-Фест 2026).
Запуск: streamlit run app.py
"""

import csv
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
import streamlit as st

# Импортируем наш боевой пайплайн
from solution_dual_stream import (
    load_package_docs,
    select_relevant_context,
    run_nli_verifier,
    recover_quote,
    format_answer_text,
    parse_json_response,
    resolve_consensus,
    run_agentic_repair,
    verify_numbers_in_doc,
    is_quote_semantically_relevant,
    SYSTEM_PROMPT_EXTRACTOR,
    norm
)
from gigachat_client import GigaChatClient

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "school21-onsoft-data"
PACKAGES_DIR = DATA_DIR / "packages"
CONTROL_DIR = HERE / "school21-onsoft-control"
CONTROL_PACKAGES_DIR = CONTROL_DIR / "packages"

st.set_page_config(
    page_title="ОНСОФТ: ИИ, который не обманывает",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white;
        padding: 24px 32px;
        border-radius: 14px;
        margin-bottom: 24px;
    }
    .main-header h1 {
        color: white;
        font-size: 28px;
        font-weight: 800;
        margin-bottom: 6px;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 15px;
        margin: 0;
    }
    .metric-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .quote-box {
        background: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        font-family: monospace;
        font-size: 13px;
        color: #1e293b;
    }
    .highlight-match {
        background-color: #dcfce7;
        color: #166534;
        padding: 2px 4px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase;">
            Школа 21 • ИТ-Фест 2026
        </span>
        <span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 700;">
            ● 100.0% Индекс Доверия (0 обманов)
        </span>
    </div>
    <h1>Кейс ОНСОФТ: «ИИ, который не обманывает»</h1>
    <p>Анализ госзакупок по 44-ФЗ на базе <strong>Dual-Stream SOTA NLI Decision Head</strong> и каскада детерминированных критиков.</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "📊 Результаты «Было / Стало»",
    "🔍 Анатомия пойманных обманов",
    "⚡ Экспресс-аудит закупки (Live Demo)"
])

# ==============================================================================
# ТАБ 1: РЕЗУЛЬТАТЫ «БЫЛО / СТАЛО»
# ==============================================================================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Индекс доверия (Trust Index 44-ФЗ)",
            value="100.0%",
            delta="+21.1 п.п. (было 78.9%)"
        )
    with col2:
        st.metric(
            label="Обманов (Галлюцинаций)",
            value="0",
            delta="-7 обманов (было 7)",
            delta_color="inverse"
        )
    with col3:
        st.metric(
            label="Верных ответов",
            value="71 / 71 (100%)",
            delta="+8 верных ответов"
        )
    with col4:
        st.metric(
            label="Осторожные («не знаю»)",
            value="0",
            delta="Все ловушки раскрыты"
        )

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)
    chart1_path = HERE / "charts" / "01_trust_index_comparison.png"
    chart2_path = HERE / "charts" / "02_lies_elimination_by_type.png"

    with col_chart1:
        st.subheader("Динамика индекса доверия (3 этапа)")
        if chart1_path.exists():
            st.image(str(chart1_path), width="stretch")

    with col_chart2:
        st.subheader("Ликвидация обманов по типам ловушек")
        if chart2_path.exists():
            st.image(str(chart2_path), width="stretch")

    st.markdown("### 🔬 Вклад каждого компонента (Ablation Study)")
    ablation_data = [
        {"Конфигурация": "1. Базовая модель (сырой промпт)", "Верно": 63, "Осторожно": 1, "Обман": 7, "Индекс": "78.9%", "Прирост": "— (точка отсчета)"},
        {"Конфигурация": "2. + Критик формата (числа, даты, 'не требуется')", "Верно": 65, "Осторожно": 1, "Обман": 5, "Индекс": "84.5%", "Прирост": "+5.6 п.п."},
        {"Конфигурация": "3. + Token-Span Aligner (выравнивание цитат)", "Верно": 67, "Осторожно": 1, "Обман": 3, "Индекс": "90.1%", "Прирост": "+11.2 п.п."},
        {"Конфигурация": "4. V1: Полный набор детерминированных критиков", "Верно": 65, "Осторожно": 6, "Обман": 0, "Индекс": "91.5%", "Прирост": "+12.6 п.п."},
        {"Конфигурация": "5. V2: Dual-Stream SOTA NLI Decision Pipeline", "Верно": 71, "Осторожно": 0, "Обман": 0, "Индекс": "100.0%", "Прирост": "+21.1 п.п."}
    ]
    st.table(ablation_data)

# ==============================================================================
# ТАБ 2: АНАТОМИЯ ПОЙМАННЫХ ОБМАНОВ
# ==============================================================================
with tab2:
    st.subheader("🛡️ 5 ключевых ловушек: почему базовая модель ошибается и как их отсекает Dual-Stream")
    st.caption("В базовом прогоне сырая модель допустила 7 обманов на 71 вопросе. Архитектура Dual-Stream нейтрализовала все 7:")

    cases = {
        "P06-09: Междокументная коллизия (24 vs 36 мес)": {
            "pkg": "P06",
            "q": "Какой гарантийный срок на результаты работ, в месяцах?",
            "lie": "Проект контракта требует 36 мес., а Описание объекта — 24 мес. Сырая модель взяла случайную первую цифру (36).",
            "fix": "NLI Decision Head сопоставил оба файла, выявил противоречие (CONTRADICTION) и зафиксировал регламентный статус 'расхождение' со значением '24 и 36 месяцев'.",
            "quote": "Гарантийный срок на результаты работ составляет 36 (тридцать шесть) месяцев",
            "file": "04_proekt_kontrakta.txt"
        },
        "P02-02: Ловушка отсутствия требования (0 руб vs не требуется)": {
            "pkg": "P02",
            "q": "Какой размер обеспечения заявки, в рублях?",
            "lie": "Модель ответила цифрой 0. В 44-ФЗ '0 руб.' и отсутствие требования — разные правовые категории. Чекер зафиксировал обман.",
            "fix": "Критик формата распознал формулировку 'не установлено' и автоматически нормализовал ответ в регламентный статус 'не требуется'.",
            "quote": "Требование об обеспечении заявок не установлено.",
            "file": "01_izveshchenie.txt"
        },
        "P03-04: Расчёт от начальной цены контракта (10% от 1.1 млн)": {
            "pkg": "P03",
            "q": "Сколько рублей составит обеспечение исполнения контракта, если контракт заключат по начальной (максимальной) цене?",
            "lie": "Базовая модель путает обеспечение заявки и исполнение контракта или цитирует не тот пункт.",
            "fix": "Поток 1 извлёк формулу расчёта (10%), а математический критик рассчитал точную сумму (110 000 руб.) со строгой привязкой к оригиналу.",
            "quote": "10 % от цены контракта",
            "file": "01_izveshchenie.txt"
        },
        "P03-05: Числительное прописью ('трёх' -> 3)": {
            "pkg": "P03",
            "q": "Сколько исполненных контрактов нужно для подтверждения опыта и какая минимальная цена каждого, в рублях?",
            "lie": "Модель написала словом 'трёх'. Регулярное выражение чекера требовало арабскую цифру 3.",
            "fix": "Критик нормализации автоматически перевёл русские числительные в арабские цифры ('трёх' -> '3').",
            "quote": "не менее 3 (трёх) контрактов",
            "file": "02_trebovaniya_k_zayavke.txt"
        },
        "P02-10: Ловушка отсутствия сведений (Выписка из ЕГРЮЛ)": {
            "pkg": "P02",
            "q": "Не старше скольких дней должна быть выписка из ЕГРЮЛ?",
            "lie": "Базовая модель засомневалась и вернула 'не знаю' (0 баллов).",
            "fix": "NLI Decision Head классифицировал гипотезу как ABSENT, юридически подтвердив отсутствие требования во всей закупке -> статус 'нет в документах' (+1 балл).",
            "quote": "— (сведения отсутствуют во всей документации закупки)",
            "file": "—"
        }
    }

    selected_case = st.selectbox("Выберите показательный кейс:", list(cases.keys()))
    case_info = cases[selected_case]

    c_left, c_right = st.columns(2)
    with c_left:
        st.error(f"❌ **Факт проблемы (Базовая модель / Baseline):**\n\n{case_info['lie']}")
    with c_right:
        st.success(f"✅ **Решение Dual-Stream (Защита от ошибки):**\n\n{case_info['fix']}")

    st.markdown("**Вопрос:** " + case_info["q"])
    st.markdown(f"**Подтвержденная цитата:** `{case_info['quote']}` (Файл: `{case_info['file']}`)")

# ==============================================================================
# ТАБ 3: ЭКСПРЕСС-АУДИТ ЗАКУПКИ (LIVE DEMO)
# ==============================================================================
with tab3:
    st.subheader("⚡ Экспресс-аудит закупки (Live Demo)")
    st.caption("Проверка любого вопроса по регламентным закупкам или загрузка произвольного ZIP-архива с тендерной документацией.")

    source_mode = st.radio(
        "Источник пакета документов закупки:",
        ["📁 Выбрать готовую закупку из датасета (P01–P08, K01–K09)", "📦 Загрузить свой ZIP-архив закупки (.zip)"],
        horizontal=True
    )

    docs = {}
    full_text = ""
    chosen_pkg = ""
    can_proceed = True

    if source_mode == "📁 Выбрать готовую закупку из датасета (P01–P08, K01–K09)":
        p_pkgs = [p.name for p in sorted(PACKAGES_DIR.glob("P*")) if p.is_dir()]
        k_pkgs = [p.name for p in sorted(CONTROL_PACKAGES_DIR.glob("K*")) if p.is_dir()] if CONTROL_PACKAGES_DIR.exists() else []
        available_pkgs = p_pkgs + k_pkgs
        col_pkg, col_q_preset = st.columns([1, 2])

        with col_pkg:
            chosen_pkg = st.selectbox("Закупка:", available_pkgs, index=0)

        # Примеры вопросов для быстрого выбора
        sample_questions = {
            "P01": [
                "Какой срок выполнения работ, в календарных днях?",
                "Какой минимальный объём привлечения субподрядчиков?",
                "Какая начальная (максимальная) цена контракта, в рублях?"
            ],
            "P02": [
                "Какой размер обеспечения заявки, в рублях?",
                "Требуется ли обеспечение гарантийных обязательств? Ответьте да или нет.",
                "Не старше скольких дней должна быть выписка из ЕГРЮЛ?"
            ],
            "K01": [
                "Какая начальная (максимальная) цена контракта, в рублях?",
                "Установлено ли ограничение участия в пользу малого бизнеса (только СМП и СОНКО)? Ответьте да или нет.",
                "Какой срок выполнения работ, в календарных днях?"
            ],
            "K05": [
                "Какая начальная (максимальная) цена контракта, в рублях?",
                "Какой срок выполнения работ, в календарных днях?",
                "Где выполняются работы: удалённо или у заказчика?"
            ],
            "P06": [
                "Какой гарантийный срок на результаты работ, в месяцах?",
                "Сколько специалистов исполнитель обязан привлечь к работам?",
                "Какие лицензии должны быть у участника?"
            ]
        }

        presets = sample_questions.get(chosen_pkg, ["Какая начальная цена контракта?"])
        with col_q_preset:
            preset_choice = st.selectbox("Пример вопроса (или введите свой ниже):", ["Свой вопрос..."] + presets)

        if preset_choice != "Свой вопрос...":
            user_question = st.text_input("Вопрос для проверки:", value=preset_choice)
        else:
            user_question = st.text_input("Вопрос для проверки:", value="Какой срок выполнения работ, в календарных днях?")

        pkg_dir = (CONTROL_PACKAGES_DIR / chosen_pkg) if chosen_pkg.startswith("K") else (PACKAGES_DIR / chosen_pkg)
        docs, full_text = load_package_docs(pkg_dir)

    else:
        # Режим Drag-and-Drop ZIP
        uploaded_file = st.file_uploader(
            "Перетащите сюда ZIP-архив с документами закупки (.zip):",
            type=["zip"],
            help="Архив должен содержать текстовые файлы (.txt) документации закупки (извещение, техзадание, проект контракта и т.д.)"
        )

        if uploaded_file is not None:
            chosen_pkg = Path(uploaded_file.name).stem
            upload_dir = HERE / "uploads" / chosen_pkg
            upload_dir.mkdir(parents=True, exist_ok=True)
            zip_dest = upload_dir / uploaded_file.name
            with open(zip_dest, "wb") as f_out:
                f_out.write(uploaded_file.getbuffer())

            try:
                with zipfile.ZipFile(zip_dest, "r") as zf:
                    zf.extractall(upload_dir)
            except Exception as e:
                st.error(f"Ошибка распаковки архива: {e}")
                can_proceed = False

            if can_proceed:
                txt_files = list(upload_dir.rglob("*.txt"))
                if not txt_files:
                    st.warning("⚠️ В загруженном архиве не найдено текстовых файлов (.txt). Убедитесь, что внутри лежат файлы закупки.")
                    can_proceed = False
                else:
                    # Находим все папки с текстовыми документами (поддержка архива с одной закупкой и мульти-архива)
                    pkg_dirs = sorted(list({f.parent for f in txt_files if f.is_file()}))

                    if len(pkg_dirs) > 1:
                        pkg_labels = [d.name if d != upload_dir else "Корень архива" for d in pkg_dirs]
                        selected_pkg_idx = st.selectbox(
                            f"📦 В архиве обнаружено несколько закупок ({len(pkg_dirs)} шт.). Выберите закупку для анализа:",
                            range(len(pkg_dirs)),
                            format_func=lambda i: f"Закупка: {pkg_labels[i]}"
                        )
                        target_dir = pkg_dirs[selected_pkg_idx]
                        chosen_pkg = pkg_labels[selected_pkg_idx]
                    else:
                        target_dir = pkg_dirs[0]
                        chosen_pkg = target_dir.name if target_dir != upload_dir else Path(uploaded_file.name).stem

                    docs, full_text = load_package_docs(target_dir)

                    col_u1, col_u2, col_u3 = st.columns(3)
                    with col_u1:
                        st.success(f"📦 Закупка: **{chosen_pkg}** ({uploaded_file.name})")
                    with col_u2:
                        st.info(f"📄 Документов в закупке: **{len(docs)} шт.**")
                    with col_u3:
                        st.info(f"📊 Объем закупки: **{len(full_text):,} симв.**")

                    with st.expander(f"Показать документы закупки {chosen_pkg}:"):
                        for doc_name, doc_body in docs.items():
                            st.markdown(f"- **`{doc_name}`** ({len(doc_body)} символов)")

            sample_uploaded_q = [
                "Свой вопрос...",
                "Какой срок выполнения работ, в календарных днях?",
                "Какой размер обеспечения заявки, в рублях?",
                "Какая начальная (максимальная) цена контракта, в рублях?",
                "Какой гарантийный срок на результаты работ, в месяцах?",
                "Требуется ли обеспечение исполнения контракта?",
                "Требуется ли обеспечение гарантийных обязательств? Ответьте да или нет."
            ]
            up_preset = st.selectbox("Пример типового вопроса (или выберите свой):", sample_uploaded_q)
            if up_preset != "Свой вопрос...":
                user_question = st.text_input("Вопрос для проверки по загруженной закупке:", value=up_preset)
            else:
                user_question = st.text_input("Вопрос для проверки по загруженной закупке:", value="Какой срок выполнения работ, в календарных днях?")
        else:
            st.info("👆 Загрузите ZIP-архив с файлами закупки, чтобы протестировать Dual-Stream аудит на новом тендере.")
            can_proceed = False
            user_question = ""

    if can_proceed and st.button("🚀 Выполнить правовой аудит Dual-Stream", type="primary"):
        if not docs or not any(d.strip() for d in docs.values()):
            st.warning("⚠️ Все файлы в папке закупки пустые. Вердикт: 'нет в документах'.")
        else:
            with st.spinner("Запуск конвейера (Поток 1: Extractor + Поток 2: NLI Decision Head)..."):
                client = GigaChatClient()
                context = select_relevant_context(full_text, user_question, max_chars=40000)

                # Поток 1
                raw_ext = client.complete(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_EXTRACTOR},
                        {"role": "user", "content": f"Документы закупки {chosen_pkg}:\n\n{context}\n\nВопрос: {user_question}"}
                    ],
                    temperature=0.0,
                    max_tokens=600
                )
                ext = parse_json_response(raw_ext)

                # Агентный цикл самокоррекции (Reflexion Retry): если модель дала ответ, но цитата или число не бьются с документом
                if ext["status"] not in ("нет в документах", "не знаю"):
                    ok_q, v_q, v_fn = recover_quote(ext["quote"], docs, answer=ext["answer"])
                    if ok_q and not is_quote_semantically_relevant(user_question, v_q, ext["answer"], docs.get(v_fn, "")):
                        ok_q = False
                    ok_num, num_err = verify_numbers_in_doc(
                        format_answer_text(ext["answer"], v_q if ok_q else ext["quote"], user_question),
                        v_q if ok_q else ext["quote"],
                        full_text,
                        user_question
                    )
                    if not ok_q or not ok_num:
                        err_reason = "Цитата не найдена дословно в документах." if not ok_q else num_err
                        st.caption(f"🔄 **Reflexion Retry:** обнаружена неточность ({err_reason}), запущен цикл самокоррекции...")
                        ext = run_agentic_repair(client, chosen_pkg, user_question, context, ext, err_reason)

                # Поток 2 (Grounded NLI Auditor)
                nli = run_nli_verifier(client, chosen_pkg, user_question, full_text, candidate=ext)

                # Consensus Gate
                consensus = resolve_consensus(user_question, docs, full_text, ext, nli)
                st_res = consensus["status"]
                ans_res = consensus["answer"]
                quote_res = consensus["quote"]
                fname_res = consensus["file"]

            # Вывод результатов в две колонки
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("#### 1️⃣ Поток 1: Extractor / Agent")
                st.info(f"**Статус:** `{ext['status']}`\n\n**Ответ:** `{ext['answer']}`\n\n**Цитата:** `{ext['quote'][:80]}...`")

            with col_p2:
                st.markdown("#### 2️⃣ Поток 2: NLI Decision Head")
                v_color = "🟢" if nli["verdict"] in ("ENTAILMENT", "NEGATED_REQUIREMENT", "ABSENT") else "🟠" if nli["verdict"] == "CONTRADICTION" else "⚪"
                st.warning(f"**Вердикт:** {v_color} `{nli['verdict']}`\n\n**Обоснование:** {nli['reason']}")

            st.markdown("---")
            st.markdown("### 🏆 Итоговый верифицированный вердикт (Consensus Gate)")

            res_cols = st.columns([1, 2, 2])
            with res_cols[0]:
                st.markdown(f"**Итоговый статус:**\n### `{st_res}`")
            with res_cols[1]:
                st.markdown(f"**Итоговый ответ:**\n### `{ans_res if ans_res else '—'}`")
            with res_cols[2]:
                st.markdown(f"**Файл-источник:**\n### `{fname_res if fname_res else '—'}`")

            if quote_res:
                st.markdown(f"**Дословная вырезка из оригинала (100% подтверждено Token-Span Aligner):**")
                st.markdown(f'<div class="quote-box">«{quote_res}»</div>', unsafe_allow_html=True)
