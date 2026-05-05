"""
XSAgent — AI 辅助小说创作系统（可视化界面）
基于 Streamlit 的交互式创作工作台

启动方式:
  streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import time
import streamlit as st
from datetime import datetime

from xsagent.core.models import (
    NovelProject, Character, WorldBuilding, OutlineNode,
    StyleGuide, CharacterRole, ChapterStatus, Foreshadowing,
    ForeshadowingStatus, StyleReference, BranchPlot, BranchStatus,
    Location, LocationStatus, Faction, FactionStatus,
    Item, ItemStatus
)
from xsagent.storage.json_storage import JSONStorage
from xsagent.skills.skill_registry import SkillRegistry
from xsagent.generator.base import GeneratorFactory
from xsagent.workflow.pipeline import CreationPipeline
from xsagent.utils.config_loader import load_config
from xsagent.utils.helpers import count_chinese_words

# ========== 页面配置 ==========
st.set_page_config(
    page_title="XSAgent 小说创作系统",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== 初始化全局组件 ==========
@st.cache_resource
def get_pipeline():
    config = load_config()
    model_cfg = config.get("model", {})
    storage_cfg = config.get("storage", {})
    skills_cfg = config.get("skills", {})

    storage_backend = storage_cfg.get("backend", "json")
    if storage_backend == "mysql":
        from xsagent.storage.mysql_storage import MySQLStorage
        storage = MySQLStorage(config=storage_cfg.get("mysql", {}))
    else:
        storage = JSONStorage(base_dir=storage_cfg.get("base_dir", "projects"))
    skill_registry = SkillRegistry()
    if skills_cfg.get("load_builtin", True):
        skill_registry.load_builtin_skills()
    for d in skills_cfg.get("custom_dirs", []):
        skill_registry.load_from_directory(d)

    generator = None
    backend = model_cfg.get("backend")
    if backend:
        try:
            generator = GeneratorFactory.create(backend, model_cfg)
        except Exception as e:
            st.sidebar.error(f"模型初始化失败: {e}")

    return CreationPipeline(
        storage=storage,
        skill_registry=skill_registry,
        generator=generator,
    )

pipeline = get_pipeline()
storage = pipeline.storage

# ========== Session State ==========
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None
if "generation_text" not in st.session_state:
    st.session_state.generation_text = ""
if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 0
if "wizard_data" not in st.session_state:
    st.session_state.wizard_data = {}


def load_project(project_id: str) -> NovelProject:
    return storage.load(project_id)


def save_project(project: NovelProject):
    project.updated_at = datetime.now().isoformat()
    storage.save(project)


def reset_wizard():
    st.session_state.wizard_step = 0
    st.session_state.wizard_data = {}


# ========== 侧边栏 ==========
st.sidebar.title("📝 XSAgent")
st.sidebar.markdown("AI 辅助小说创作系统")
st.sidebar.divider()

# 项目选择
projects = storage.list_projects()
project_options = {pid: (storage.load(pid).title if storage.load(pid) else pid) for pid in projects}

# 如果在向导中，侧边栏只显示向导信息；否则显示项目选择
if st.session_state.wizard_step > 0:
    st.sidebar.info("正在创建新小说...")
    st.sidebar.write(f"步骤 {st.session_state.wizard_step} / 4")
    if st.sidebar.button("取消创建"):
        reset_wizard()
        st.rerun()
else:
    selected_project_name = st.sidebar.selectbox(
        "选择项目",
        options=["-- 新建项目 --"] + list(project_options.keys()),
        format_func=lambda x: "新建项目" if x == "-- 新建项目 --" else f"{project_options.get(x, x)} ({x[:6]}...)",
        index=(list(project_options.keys()).index(st.session_state.current_project_id) + 1)
        if st.session_state.current_project_id in project_options else 0,
    )

    if selected_project_name == "-- 新建项目 --":
        st.sidebar.subheader("新建项目")
        if st.sidebar.button("开始创建新小说", type="primary"):
            st.session_state.wizard_step = 1
            st.rerun()
    else:
        st.session_state.current_project_id = selected_project_name

st.sidebar.divider()

# 导航菜单（仅在非向导模式下显示）
page = None
if st.session_state.wizard_step == 0 and st.session_state.current_project_id:
    page = st.sidebar.radio(
        "导航",
        ["项目概览", "世界观设定", "地点管理", "势力管理", "人物设定", "物品定义", "故事大纲", "伏笔设计", "风格设定", "章节创作", "导出小说"],
    )

# ========== 主内容区 ==========

# ---------- 欢迎页 ----------
if st.session_state.wizard_step == 0 and not st.session_state.current_project_id:
    st.title("📝 欢迎来到 XSAgent")
    st.markdown("AI 辅助小说创作系统 — 你的故事，由你主宰")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📚 继续创作")
        if project_options:
            selected = st.selectbox(
                "选择已有小说",
                options=list(project_options.keys()),
                format_func=lambda x: project_options.get(x, x),
            )
            if st.button("进入项目", use_container_width=True):
                st.session_state.current_project_id = selected
                st.rerun()
        else:
            st.info("暂无已有小说")

    with col2:
        st.subheader("✨ 新建小说")
        st.write("遵循四步流程创建全新小说：")
        st.write("1. 输入小说名称与基本信息")
        st.write("2. 设定世界观")
        st.write("3. 设计故事大纲")
        st.write("4. 编写第一章情节流程")
        if st.button("开始创建", type="primary", use_container_width=True):
            st.session_state.wizard_step = 1
            st.rerun()

    st.stop()


# ---------- 三步向导 ----------
if st.session_state.wizard_step > 0:
    step = st.session_state.wizard_step
    st.title("✨ 创建新小说")
    progress_text = (
        "填写基本信息" if step == 1 else
        ("设定世界观" if step == 2 else
        ("设计故事大纲" if step == 3 else "编写第一章情节"))
    )
    st.progress(step / 4, text=f"步骤 {step} / 4 — {progress_text}")

    # ===== Step 1: 基本信息 =====
    if step == 1:
        st.header("第一步：小说基本信息")
        with st.form("wizard_step1"):
            title = st.text_input("小说名称 *", value=st.session_state.wizard_data.get("title", ""))
            author = st.text_input("作者", value=st.session_state.wizard_data.get("author", ""))
            genre = st.text_input("题材类型", value=st.session_state.wizard_data.get("genre", ""), placeholder="玄幻 / 科幻 / 都市 / 武侠...")
            desc = st.text_area("简介", value=st.session_state.wizard_data.get("desc", ""))
            col_back, col_next = st.columns([1, 1])
            with col_back:
                if st.form_submit_button("取消", use_container_width=True):
                    reset_wizard()
                    st.rerun()
            with col_next:
                if st.form_submit_button("下一步：设定世界观", type="primary", use_container_width=True):
                    if not title.strip():
                        st.error("小说名称不能为空")
                    else:
                        st.session_state.wizard_data.update({"title": title, "author": author, "genre": genre, "desc": desc})
                        st.session_state.wizard_step = 2
                        st.rerun()
        st.stop()

    # ===== Step 2: 世界观设定 =====
    elif step == 2:
        st.header("第二步：世界观设定")
        st.info("详细的世界观设定将作为 AI 生成内容的核心约束。所有字段均可后续修改。")

        with st.form("wizard_world_form"):
            w_name = st.text_input("世界名称", value=st.session_state.wizard_data.get("title", ""))
            w_genre = st.text_input("题材类型", value=st.session_state.wizard_data.get("genre", ""), placeholder="玄幻 / 科幻 / 都市 / 武侠...")
            w_era = st.text_input("时代背景", value=st.session_state.wizard_data.get("world_era", ""), placeholder="如：架空古代 / 2145年未来地球")
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                w_geography = st.text_area("地理设定", value=st.session_state.wizard_data.get("world_geography", ""), height=100, placeholder="大陆分布、气候、地形等")
                w_history = st.text_area("历史沿革", value=st.session_state.wizard_data.get("world_history", ""), height=100, placeholder="重大历史事件、朝代更替等")
                w_power = st.text_area("力量体系 / 科技水平", value=st.session_state.wizard_data.get("world_power_system", ""), height=100, placeholder="修炼境界、魔法体系、科技程度等")
            with col_w2:
                w_society = st.text_area("社会结构 / 势力分布", value=st.session_state.wizard_data.get("world_society", ""), height=100, placeholder="阶级、政体、门派、公司等")
                w_rules = st.text_area("核心规则（每行一条）", value="\n".join(st.session_state.wizard_data.get("world_rules", [])), height=100, placeholder="如：魔法师每日施法上限为3次")
                w_customs = st.text_area("风俗文化（每行一条）", value="\n".join(st.session_state.wizard_data.get("world_customs", [])), height=100, placeholder="如：新年要放天灯祈福")

            w_locations = st.text_area("关键地点（格式: 地名=描述，每行一个）", value="\n".join(f"{k}={v}" for k, v in st.session_state.wizard_data.get("world_locations", {}).items()), height=80)
            w_factions = st.text_area("势力/组织（格式: 名称=描述，每行一个）", value="\n".join(f"{k}={v}" for k, v in st.session_state.wizard_data.get("world_factions", {}).items()), height=80)
            w_notes = st.text_area("世界观备忘笔记", value=st.session_state.wizard_data.get("world_notes", ""), height=60)
            w_tags = st.text_input("标签（逗号分隔）", value=", ".join(st.session_state.wizard_data.get("world_tags", [])), placeholder="修仙, 架空, 权谋...")

            col_back, col_next = st.columns([1, 1])
            with col_back:
                if st.form_submit_button("上一步", use_container_width=True):
                    st.session_state.wizard_step = 1
                    st.rerun()
            with col_next:
                if st.form_submit_button("下一步：设计大纲", type="primary", use_container_width=True):
                    st.session_state.wizard_data.update({
                        "world_name": w_name,
                        "genre": w_genre,
                        "world_era": w_era,
                        "world_geography": w_geography,
                        "world_history": w_history,
                        "world_power_system": w_power,
                        "world_society": w_society,
                        "world_rules": [r.strip() for r in w_rules.splitlines() if r.strip()],
                        "world_customs": [c.strip() for c in w_customs.splitlines() if c.strip()],
                        "world_locations": {k.strip(): v.strip() for line in w_locations.splitlines() if "=" in line for k, v in [line.split("=", 1)]},
                        "world_factions": {k.strip(): v.strip() for line in w_factions.splitlines() if "=" in line for k, v in [line.split("=", 1)]},
                        "world_notes": w_notes,
                        "world_tags": [t.strip() for t in w_tags.split(",") if t.strip()],
                    })
                    st.session_state.wizard_step = 3
                    st.rerun()
        st.stop()

    # ===== Step 3: 故事大纲 =====
    elif step == 3:
        st.header("第三步：故事大纲")
        st.info("大纲分为「总纲-卷-幕-章」四级结构。此处只需规划到「卷」级别，描述每卷的大体流程即可。幕与章可在后续创作中逐步细化。高级用户也可通过 JSON 导入含幕/章的详细大纲。")

        tab_form, tab_json = st.tabs(["表单输入", "JSON导入"])

        with tab_form:
            with st.form("wizard_outline_form"):
                st.markdown("**卷列表**（每行一卷，格式：`卷标题|摘要`）")
                volume_lines = st.text_area(
                    "卷",
                    value="第一卷：暗流|故事从这里开始\n第二卷：风云|冲突逐渐升级",
                    height=150,
                )
                col_back, col_next = st.columns([1, 1])
                with col_back:
                    if st.form_submit_button("上一步", use_container_width=True):
                        st.session_state.wizard_step = 2
                        st.rerun()
                with col_next:
                    if st.form_submit_button("下一步：第一章情节", type="primary", use_container_width=True):
                        children = []
                        for line in volume_lines.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.split("|", 1)
                            vol_title = parts[0].strip()
                            vol_summary = parts[1].strip() if len(parts) > 1 else ""
                            children.append(OutlineNode(
                                title=vol_title, level=1, summary=vol_summary
                            ))
                        outline = OutlineNode(
                            title="全书总纲", level=0, summary="", children=children
                        )
                        st.session_state.wizard_data["outline"] = outline.to_dict()
                        st.session_state.wizard_step = 4
                        st.rerun()

        with tab_json:
            with st.form("wizard_outline_json"):
                json_text = st.text_area("粘贴大纲 JSON", height=200)
                col_back, col_next = st.columns([1, 1])
                with col_back:
                    if st.form_submit_button("上一步", use_container_width=True):
                        st.session_state.wizard_step = 2
                        st.rerun()
                with col_next:
                    if st.form_submit_button("下一步：第一章情节", type="primary", use_container_width=True):
                        try:
                            data = json.loads(json_text)
                            outline = OutlineNode.from_dict(data)
                            # 兼容旧数据：如果根节点 level != 0，自动包装为总纲
                            if outline.level != 0:
                                old_root = outline
                                outline = OutlineNode(
                                    title="全书总纲", level=0, summary="", children=[old_root]
                                )
                            st.session_state.wizard_data["outline"] = outline.to_dict()
                            st.session_state.wizard_step = 4
                            st.rerun()
                        except Exception as e:
                            st.error(f"JSON 解析失败: {e}")
        st.stop()

    # ===== Step 4: 第一章情节流程 =====
    elif step == 4:
        st.header("第四步：第一章情节流程")
        st.info("明确第一章的核心要素，这些信息将作为 AI 生成内容的核心约束。若大纲未包含章节，系统将自动为你创建第一章。")

        with st.form("wizard_chapter1"):
            ch1_title = st.text_input("章节标题", value="第一章")
            ch1_summary = st.text_area("本章摘要", height=80)
            ch1_plot_points = st.text_area("情节点（每行一个）", height=100)
            ch1_emotion = st.text_input("情感基调", placeholder="如：紧张中带希望")
            ch1_chars = st.text_input("出场人物（逗号分隔）", placeholder="主角名, 配角A, 反派X")
            ch1_locations = st.text_input("场景地点（逗号分隔）")

            col_back, col_create = st.columns([1, 1])
            with col_back:
                if st.form_submit_button("上一步", use_container_width=True):
                    st.session_state.wizard_step = 3
                    st.rerun()
            with col_create:
                if st.form_submit_button("创建小说并进入创作", type="primary", use_container_width=True):
                    # 创建项目
                    proj = pipeline.initialize_project(
                        title=st.session_state.wizard_data["title"],
                        author=st.session_state.wizard_data.get("author", ""),
                        description=st.session_state.wizard_data.get("desc", ""),
                    )
                    # 设置完整世界观
                    world_data = st.session_state.wizard_data
                    world = WorldBuilding(
                        name=world_data.get("world_name", world_data["title"]),
                        genre=world_data.get("genre", ""),
                        era=world_data.get("world_era", ""),
                        geography=world_data.get("world_geography", ""),
                        history=world_data.get("world_history", ""),
                        power_system=world_data.get("world_power_system", ""),
                        society=world_data.get("world_society", ""),
                        rules=world_data.get("world_rules", []),
                        locations=world_data.get("world_locations", {}),
                        factions=world_data.get("world_factions", {}),
                        customs=world_data.get("world_customs", []),
                        notes=world_data.get("world_notes", ""),
                        tags=world_data.get("world_tags", []),
                    )
                    proj.world = world
                    # 设置大纲
                    outline = OutlineNode.from_dict(st.session_state.wizard_data["outline"])
                    pipeline.set_outline(proj, outline)
                    # 获取或创建第一章
                    if proj.chapters:
                        ch1 = sorted(proj.chapters.values(), key=lambda c: c.sequence_number)[0]
                    else:
                        ch1 = pipeline.add_chapter(proj, title=ch1_title, outline_summary=ch1_summary)
                    # 更新第一章信息
                    ch1.outline_summary = ch1_summary
                    ch1.notes = f"情感基调: {ch1_emotion}\n情节点:\n{ch1_plot_points}"
                    if ch1_chars:
                        # 先创建人物占位（简化处理：只记录名字）
                        for cname in [n.strip() for n in ch1_chars.split(",") if n.strip()]:
                            exists = any(char.name == cname for char in proj.characters.values())
                            if not exists:
                                char = pipeline.add_character(proj, name=cname, role=CharacterRole.SUPPORTING)
                                ch1.characters_present.append(char.id)
                    if ch1_locations:
                        ch1.locations = [loc.strip() for loc in ch1_locations.split(",") if loc.strip()]
                    save_project(proj)

                    st.session_state.current_project_id = proj.id
                    reset_wizard()
                    st.success("小说创建成功！")
                    st.rerun()
        st.stop()


# ---------- 正常项目页面 ----------
if not st.session_state.current_project_id:
    st.info("请从侧边栏选择一个项目或创建新项目")
    st.stop()

project = load_project(st.session_state.current_project_id)
if not project:
    st.error("项目加载失败")
    st.stop()


# ---------- 页面：项目概览 ----------
if page == "项目概览":
    st.header(f"《{project.title}》")
    cols = st.columns(4)
    stats = pipeline.get_project_stats(project)
    cols[0].metric("总章节", stats["total_chapters"])
    cols[1].metric("已完成", stats["completed_chapters"])
    cols[2].metric("总字数", f"{stats['total_words']:,}")
    cols[3].metric("人物数", stats["character_count"])

    st.divider()
    st.subheader("章节进度")
    if project.chapters:
        for ch in sorted(project.chapters.values(), key=lambda c: c.sequence_number):
            status_color = {"completed": "🟢", "review": "🟡", "writing": "🔵", "planned": "⚪"}.get(ch.status.value, "⚪")
            cols_inner = st.columns([1, 4, 2, 2])
            cols_inner[0].write(f"{status_color} 第{ch.sequence_number}章")
            cols_inner[1].write(f"《{ch.title}》")
            cols_inner[2].write(ch.status.value)
            cols_inner[3].write(f"{ch.word_count} 字")
    else:
        st.info("暂无章节，请先在【故事大纲】中导入或创建大纲")


# ---------- 页面：世界观设定 ----------
elif page == "世界观设定":
    st.header("世界观设定")
    world = project.world or WorldBuilding()
    with st.form("world_form"):
        name = st.text_input("世界名称", value=world.name)
        genre = st.text_input("题材类型", value=world.genre, placeholder="玄幻 / 科幻 / 都市 / 武侠...")
        era = st.text_input("时代背景", value=world.era)
        col1, col2 = st.columns(2)
        with col1:
            geography = st.text_area("地理设定", value=world.geography, height=100)
            history = st.text_area("历史沿革", value=world.history, height=100)
            power_system = st.text_area("力量体系 / 科技水平", value=world.power_system, height=100)
        with col2:
            society = st.text_area("社会结构 / 势力分布", value=world.society, height=100)
            rules_text = st.text_area("核心规则（每行一条）", value="\n".join(world.rules), height=100)
            customs_text = st.text_area("风俗文化（每行一条）", value="\n".join(world.customs), height=100)

        notes = st.text_area("世界观备忘笔记", value=world.notes, height=60)
        tags_text = st.text_input("标签（逗号分隔）", value=", ".join(world.tags), placeholder="修仙, 架空, 权谋...")

        if st.form_submit_button("保存世界观"):
            world.name = name
            world.genre = genre
            world.era = era
            world.geography = geography
            world.history = history
            world.power_system = power_system
            world.society = society
            world.rules = [r.strip() for r in rules_text.splitlines() if r.strip()]
            world.customs = [c.strip() for c in customs_text.splitlines() if c.strip()]
            world.notes = notes
            world.tags = [t.strip() for t in tags_text.split(",") if t.strip()]
            project.world = world
            save_project(project)
            st.success("世界观已保存")

    st.divider()
    st.info("💡 地点与势力已迁移至独立管理页面，请通过左侧导航「地点管理」和「势力管理」进行详细设定。")


# ---------- 页面：地点管理 ----------
elif page == "地点管理":
    st.header("地点管理")

    tab_list, tab_add = st.tabs(["地点列表", "添加地点"])

    with tab_list:
        if not project.locations:
            st.info("暂无地点，请在「添加地点」中手动添加，或通过章节审校让AI自动识别。")
        else:
            # 按层级排序展示
            for loc in sorted(project.locations.values(), key=lambda x: x.hierarchy or x.name):
                with st.expander(f"📍 {loc.name} [{loc.status.value}]"):
                    with st.form(f"edit_loc_form_{loc.id}"):
                        lname = st.text_input("地点名称", value=loc.name, key=f"loc_name_{loc.id}")
                        ldesc = st.text_area("描述", value=loc.description, height=60, key=f"loc_desc_{loc.id}")
                        lstatus = st.selectbox(
                            "状态",
                            [LocationStatus.ACTIVE, LocationStatus.DESTROYED, LocationStatus.HIDDEN, LocationStatus.LOST, LocationStatus.UNDER_CONSTRUCTION],
                            index=[LocationStatus.ACTIVE, LocationStatus.DESTROYED, LocationStatus.HIDDEN, LocationStatus.LOST, LocationStatus.UNDER_CONSTRUCTION].index(loc.status),
                            format_func=lambda s: {"active": "正常", "destroyed": "已毁灭", "hidden": "隐藏", "lost": "失落", "under_construction": "建造中"}.get(s.value, s.value),
                            key=f"loc_status_{loc.id}",
                        )
                        llevel = st.selectbox("级别", ["minor", "normal", "important", "core", "sacred"], index=["minor", "normal", "important", "core", "sacred"].index(loc.level) if loc.level in ["minor", "normal", "important", "core", "sacred"] else 1, key=f"loc_level_{loc.id}")
                        lscale = st.text_input("规模", value=loc.scale, key=f"loc_scale_{loc.id}")
                        lhierarchy = st.text_input("层级位置", value=loc.hierarchy, placeholder="如: 东方大陆 > 青云国 > 京城", key=f"loc_hier_{loc.id}")
                        # 父地点选择
                        parent_options = {"": "（无）"}
                        for pid, ploc in project.locations.items():
                            if pid != loc.id:
                                parent_options[pid] = ploc.name
                        lparent = st.selectbox(
                            "上级地点",
                            options=list(parent_options.keys()),
                            index=list(parent_options.keys()).index(loc.parent_location_id) if loc.parent_location_id in parent_options else 0,
                            format_func=lambda x: parent_options[x],
                            key=f"loc_parent_{loc.id}",
                        )
                        lnotes = st.text_area("备忘", value=loc.notes, height=40, key=f"loc_notes_{loc.id}")

                        if st.form_submit_button("保存修改"):
                            loc.name = lname
                            loc.description = ldesc
                            loc.status = lstatus
                            loc.level = llevel
                            loc.scale = lscale
                            loc.hierarchy = lhierarchy
                            loc.parent_location_id = lparent if lparent else None
                            loc.notes = lnotes
                            save_project(project)
                            st.success(f"地点 {lname} 已更新")
                            st.rerun()

                    if st.button("删除地点", key=f"del_loc_{loc.id}", type="secondary"):
                        del project.locations[loc.id]
                        save_project(project)
                        st.success(f"地点 {loc.name} 已删除")
                        st.rerun()

    with tab_add:
        with st.form("add_location"):
            lname = st.text_input("地点名称 *")
            ldesc = st.text_area("描述")
            lstatus = st.selectbox("状态", [LocationStatus.ACTIVE, LocationStatus.DESTROYED, LocationStatus.HIDDEN, LocationStatus.LOST, LocationStatus.UNDER_CONSTRUCTION], format_func=lambda s: {"active": "正常", "destroyed": "已毁灭", "hidden": "隐藏", "lost": "失落", "under_construction": "建造中"}.get(s.value, s.value))
            llevel = st.selectbox("级别", ["minor", "normal", "important", "core", "sacred"])
            lscale = st.text_input("规模", placeholder="如: 中型城市 / 大型宗门")
            lhierarchy = st.text_input("层级位置", placeholder="如: 东方大陆 > 青云国 > 京城")
            lnotes = st.text_area("备忘", height=40)
            if st.form_submit_button("添加") and lname:
                loc = Location(
                    name=lname, description=ldesc, status=lstatus,
                    level=llevel, scale=lscale, hierarchy=lhierarchy, notes=lnotes,
                )
                project.locations[loc.id] = loc
                save_project(project)
                st.success(f"地点 {lname} 已添加")
                st.rerun()


# ---------- 页面：势力管理 ----------
elif page == "势力管理":
    st.header("势力管理")

    tab_list, tab_add = st.tabs(["势力列表", "添加势力"])

    with tab_list:
        if not project.factions:
            st.info("暂无势力，请在「添加势力」中手动添加，或通过章节审校让AI自动识别。")
        else:
            for fac in sorted(project.factions.values(), key=lambda x: x.name):
                loc_name = project.locations[fac.location_id].name if fac.location_id and fac.location_id in project.locations else "未绑定地点"
                with st.expander(f"🏛️ {fac.name} [{fac.status.value}] — 📍 {loc_name}"):
                    with st.form(f"edit_fac_form_{fac.id}"):
                        fname = st.text_input("势力名称", value=fac.name, key=f"fac_name_{fac.id}")
                        fdesc = st.text_area("描述", value=fac.description, height=60, key=f"fac_desc_{fac.id}")
                        fstatus = st.selectbox(
                            "状态",
                            [FactionStatus.ACTIVE, FactionStatus.DISSOLVED, FactionStatus.HIDDEN, FactionStatus.AT_WAR, FactionStatus.DECLINING, FactionStatus.RISING],
                            index=[FactionStatus.ACTIVE, FactionStatus.DISSOLVED, FactionStatus.HIDDEN, FactionStatus.AT_WAR, FactionStatus.DECLINING, FactionStatus.RISING].index(fac.status),
                            format_func=lambda s: {"active": "活跃", "dissolved": "已解散", "hidden": "隐秘", "at_war": "交战中", "declining": "衰落中", "rising": "崛起中"}.get(s.value, s.value),
                            key=f"fac_status_{fac.id}",
                        )
                        flevel = st.selectbox("级别", ["minor", "normal", "important", "major", "supreme"], index=["minor", "normal", "important", "major", "supreme"].index(fac.level) if fac.level in ["minor", "normal", "important", "major", "supreme"] else 1, key=f"fac_level_{fac.id}")
                        # 绑定地点
                        loc_options = {"": "（无）"}
                        for lid, lloc in project.locations.items():
                            loc_options[lid] = lloc.name
                        floc_id = st.selectbox(
                            "绑定地点",
                            options=list(loc_options.keys()),
                            index=list(loc_options.keys()).index(fac.location_id) if fac.location_id in loc_options else 0,
                            format_func=lambda x: loc_options[x],
                            key=f"fac_loc_{fac.id}",
                        )
                        # 首领人物
                        char_options = {"": "（无）"}
                        for cid, cchar in project.characters.items():
                            char_options[cid] = cchar.name
                        fleader_id = st.selectbox(
                            "首领",
                            options=list(char_options.keys()),
                            index=list(char_options.keys()).index(fac.leader_character_id) if fac.leader_character_id in char_options else 0,
                            format_func=lambda x: char_options[x],
                            key=f"fac_leader_{fac.id}",
                        )
                        fnotes = st.text_area("备忘", value=fac.notes, height=40, key=f"fac_notes_{fac.id}")

                        if st.form_submit_button("保存修改"):
                            fac.name = fname
                            fac.description = fdesc
                            fac.status = fstatus
                            fac.level = flevel
                            fac.location_id = floc_id if floc_id else None
                            fac.leader_character_id = fleader_id if fleader_id else None
                            fac.notes = fnotes
                            save_project(project)
                            st.success(f"势力 {fname} 已更新")
                            st.rerun()

                    if st.button("删除势力", key=f"del_fac_{fac.id}", type="secondary"):
                        del project.factions[fac.id]
                        save_project(project)
                        st.success(f"势力 {fac.name} 已删除")
                        st.rerun()

    with tab_add:
        with st.form("add_faction"):
            fname = st.text_input("势力名称 *")
            fdesc = st.text_area("描述")
            fstatus = st.selectbox("状态", [FactionStatus.ACTIVE, FactionStatus.DISSOLVED, FactionStatus.HIDDEN, FactionStatus.AT_WAR, FactionStatus.DECLINING, FactionStatus.RISING], format_func=lambda s: {"active": "活跃", "dissolved": "已解散", "hidden": "隐秘", "at_war": "交战中", "declining": "衰落中", "rising": "崛起中"}.get(s.value, s.value))
            flevel = st.selectbox("级别", ["minor", "normal", "important", "major", "supreme"])
            # 绑定地点
            loc_options = {"": "（无）"}
            for lid, lloc in project.locations.items():
                loc_options[lid] = lloc.name
            floc_id = st.selectbox("绑定地点", options=list(loc_options.keys()), format_func=lambda x: loc_options[x])
            fnotes = st.text_area("备忘", height=40)
            if st.form_submit_button("添加") and fname:
                fac = Faction(
                    name=fname, description=fdesc, status=fstatus,
                    level=flevel, location_id=floc_id if floc_id else None, notes=fnotes,
                )
                project.factions[fac.id] = fac
                save_project(project)
                st.success(f"势力 {fname} 已添加")
                st.rerun()


# ---------- 页面：人物设定 ----------
elif page == "人物设定":
    st.header("人物设定")
    tab_list, tab_add = st.tabs(["人物列表", "添加人物"])

    with tab_list:
        if not project.characters:
            st.info("暂无人物")
        for char in project.characters.values():
            fac_name = project.factions[char.faction_id].name if char.faction_id and char.faction_id in project.factions else ""
            with st.expander(f"【{char.name}】{char.role.value}" + (f" — 🏛️ {fac_name}" if fac_name else "")):
                with st.form(f"edit_char_form_{char.id}"):
                    cname = st.text_input("姓名", value=char.name, key=f"char_name_{char.id}")
                    calias = st.text_input("别名/称号（逗号分隔）", value=", ".join(char.alias), key=f"char_alias_{char.id}")
                    crole = st.selectbox(
                        "角色定位",
                        options=[r.value for r in CharacterRole],
                        index=[r.value for r in CharacterRole].index(char.role.value),
                        key=f"char_role_{char.id}",
                    )
                    # 势力绑定
                    fac_options = {"": "（无）"}
                    for fid, fac in project.factions.items():
                        fac_options[fid] = fac.name
                    cfaction_id = st.selectbox(
                        "核心绑定势力",
                        options=list(fac_options.keys()),
                        index=list(fac_options.keys()).index(char.faction_id) if char.faction_id in fac_options else 0,
                        format_func=lambda x: fac_options[x],
                        key=f"char_faction_{char.id}",
                    )
                    cfaction_notes = st.text_input("势力关系描述", value=char.faction_notes, placeholder="如: 核心成员 / 外围弟子 / 敌对", key=f"char_faction_notes_{char.id}")
                    col1, col2 = st.columns(2)
                    with col1:
                        cage = st.number_input("年龄", value=char.age or 0, min_value=0, key=f"char_age_{char.id}")
                        cappearance = st.text_area("外貌描写", value=char.appearance, height=80, key=f"char_appearance_{char.id}")
                        cpersonality = st.text_area("性格特征", value=char.personality, height=80, key=f"char_personality_{char.id}")
                        cmotivation = st.text_area("核心动机", value=char.motivation, height=80, key=f"char_motivation_{char.id}")
                    with col2:
                        cgender = st.text_input("性别", value=char.gender or "", key=f"char_gender_{char.id}")
                        cbackground = st.text_area("身世背景", value=char.background, height=80, key=f"char_background_{char.id}")
                        carc = st.text_area("人物弧线", value=char.arc, height=80, key=f"char_arc_{char.id}")
                        cnotes = st.text_area("备忘笔记", value=char.notes, height=80, key=f"char_notes_{char.id}")
                        cspells_skills = st.text_area("法术/技能", value=char.spells_skills, height=80, key=f"char_spells_skills_{char.id}")
                    cabilities = st.text_input("能力/技能（逗号分隔）", value=", ".join(char.abilities), key=f"char_abilities_{char.id}")
                    crels = st.text_input("关系网（格式: 角色名=关系，逗号分隔）", value=", ".join(f"{k}={v}" for k, v in char.relationships.items()), key=f"char_rels_{char.id}")
                    ctags = st.text_input("标签（逗号分隔）", value=", ".join(char.tags), key=f"char_tags_{char.id}")

                    if st.form_submit_button("保存修改"):
                        char.name = cname
                        char.alias = [a.strip() for a in calias.split(",") if a.strip()]
                        char.role = CharacterRole(crole)
                        char.faction_id = cfaction_id if cfaction_id else None
                        char.faction_notes = cfaction_notes
                        char.age = cage if cage > 0 else None
                        char.gender = cgender or None
                        char.appearance = cappearance
                        char.personality = cpersonality
                        char.background = cbackground
                        char.motivation = cmotivation
                        char.arc = carc
                        char.spells_skills = cspells_skills
                        char.abilities = [a.strip() for a in cabilities.split(",") if a.strip()]
                        char.notes = cnotes
                        char.tags = [t.strip() for t in ctags.split(",") if t.strip()]
                        char.relationships = {}
                        for item in crels.split(","):
                            if "=" in item:
                                k, v = item.split("=", 1)
                                char.relationships[k.strip()] = v.strip()
                        project.updated_at = datetime.now().isoformat()
                        save_project(project)
                        st.success(f"人物 {cname} 已更新")
                        st.rerun()

                # 删除按钮放在表单外
                if st.button("删除人物", key=f"del_char_{char.id}", type="secondary"):
                    if char.id in project.characters:
                        del project.characters[char.id]
                        save_project(project)
                        st.success(f"人物 {char.name} 已删除")
                        st.rerun()

    with tab_add:
        with st.form("add_character"):
            cname = st.text_input("姓名")
            crole = st.selectbox("角色定位", options=[r.value for r in CharacterRole])
            # 势力绑定
            fac_options = {"": "（无）"}
            for fid, fac in project.factions.items():
                fac_options[fid] = fac.name
            cfaction_id = st.selectbox("核心绑定势力", options=list(fac_options.keys()), format_func=lambda x: fac_options[x])
            cfaction_notes = st.text_input("势力关系描述", placeholder="如: 核心成员 / 外围弟子")
            cpersonality = st.text_area("性格特征")
            cmotivation = st.text_area("核心动机")
            cbackground = st.text_area("身世背景")
            carc = st.text_area("人物弧线")
            cspells_skills = st.text_area("法术/技能")
            if st.form_submit_button("添加") and cname:
                char = pipeline.add_character(
                    project, name=cname, role=CharacterRole(crole),
                    personality=cpersonality, motivation=cmotivation,
                    background=cbackground, arc=carc,
                    spells_skills=cspells_skills,
                )
                if cfaction_id:
                    char.faction_id = cfaction_id
                    char.faction_notes = cfaction_notes
                    save_project(project)
                st.success(f"人物 {cname} 已添加")
                st.rerun()


# ---------- 页面：物品定义 ----------
elif page == "物品定义":
    st.header("物品定义")

    ITEM_TYPE_OPTIONS = ["artifact", "weapon", "armor", "consumable", "material", "treasure", "other"]
    ITEM_TYPE_LABELS = {"artifact": "法宝", "weapon": "武器", "armor": "护具", "consumable": "消耗品", "material": "材料", "treasure": "宝物", "other": "其他"}
    GRADE_OPTIONS = ["nothing", "common", "uncommon", "rare", "epic", "legendary", "divine"]
    GRADE_LABELS = {"nothing":"无品级","common": "凡品", "uncommon": "法品", "rare": "灵品", "epic": "宝品", "legendary": "道品", "divine": "仙品"}
    ITEM_STATUS_LIST = [ItemStatus.NOTHING,ItemStatus.ACTIVE, ItemStatus.LOST, ItemStatus.DESTROYED, ItemStatus.SEALED, ItemStatus.DORMANT]
    ITEM_STATUS_LABELS = {"nothing":"无状态","active": "正常", "lost": "已遗失", "destroyed": "已损毁", "sealed": "封印中", "dormant": "潜伏/未觉醒"}

    tab_list, tab_add = st.tabs(["物品列表", "添加物品"])

    with tab_list:
        if not project.items:
            st.info("暂无物品，请在「添加物品」中手动添加。")
        else:
            for item in sorted(project.items.values(), key=lambda x: (GRADE_OPTIONS.index(x.grade) if x.grade in GRADE_OPTIONS else 0, x.name), reverse=True):
                owner_name = ""
                if item.owner_character_id and item.owner_character_id in project.characters:
                    owner_name = project.characters[item.owner_character_id].name
                loc_name = ""
                if item.location_id and item.location_id in project.locations:
                    loc_name = project.locations[item.location_id].name
                grade_label = GRADE_LABELS.get(item.grade, item.grade)
                type_label = ITEM_TYPE_LABELS.get(item.item_type, item.item_type)
                header = f"⚔️ {item.name} [{grade_label}] ({type_label})"
                if owner_name:
                    header += f" — 👤 {owner_name}"
                with st.expander(header):
                    with st.form(f"edit_item_form_{item.id}"):
                        iname = st.text_input("物品名称", value=item.name, key=f"item_name_{item.id}")
                        idesc = st.text_area("描述", value=item.description, height=60, key=f"item_desc_{item.id}")
                        col1, col2 = st.columns(2)
                        with col1:
                            itype = st.selectbox(
                                "类型", ITEM_TYPE_OPTIONS,
                                index=ITEM_TYPE_OPTIONS.index(item.item_type) if item.item_type in ITEM_TYPE_OPTIONS else 0,
                                format_func=lambda x: ITEM_TYPE_LABELS.get(x, x),
                                key=f"item_type_{item.id}",
                            )
                            istatus = st.selectbox(
                                "状态", ITEM_STATUS_LIST,
                                index=ITEM_STATUS_LIST.index(item.status),
                                format_func=lambda s: ITEM_STATUS_LABELS.get(s.value, s.value),
                                key=f"item_status_{item.id}",
                            )
                        with col2:
                            igrade = st.selectbox(
                                "品级", GRADE_OPTIONS,
                                index=GRADE_OPTIONS.index(item.grade) if item.grade in GRADE_OPTIONS else 1,
                                format_func=lambda x: GRADE_LABELS.get(x, x),
                                key=f"item_grade_{item.id}",
                            )
                            # 持有者选择
                            char_options = {"": "（无）"}
                            for cid, cchar in project.characters.items():
                                char_options[cid] = cchar.name
                            iowner = st.selectbox(
                                "持有者",
                                options=list(char_options.keys()),
                                index=list(char_options.keys()).index(item.owner_character_id) if item.owner_character_id in char_options else 0,
                                format_func=lambda x: char_options[x],
                                key=f"item_owner_{item.id}",
                            )
                        ieffects = st.text_area("功效/能力", value=item.effects, height=60, key=f"item_effects_{item.id}")
                        iorigin = st.text_input("来源/出处", value=item.origin, key=f"item_origin_{item.id}")
                        # 所在地点
                        loc_options = {"": "（无）"}
                        for lid, lloc in project.locations.items():
                            loc_options[lid] = lloc.name
                        iloc = st.selectbox(
                            "所在地点",
                            options=list(loc_options.keys()),
                            index=list(loc_options.keys()).index(item.location_id) if item.location_id in loc_options else 0,
                            format_func=lambda x: loc_options[x],
                            key=f"item_loc_{item.id}",
                        )
                        itags = st.text_input("标签（逗号分隔）", value=", ".join(item.tags), key=f"item_tags_{item.id}")
                        inotes = st.text_area("备忘", value=item.notes, height=40, key=f"item_notes_{item.id}")

                        if st.form_submit_button("保存修改"):
                            item.name = iname
                            item.description = idesc
                            item.item_type = itype
                            item.grade = igrade
                            item.effects = ieffects
                            item.origin = iorigin
                            item.owner_character_id = iowner if iowner else None
                            item.location_id = iloc if iloc else None
                            item.status = istatus
                            item.tags = [t.strip() for t in itags.split(",") if t.strip()]
                            item.notes = inotes
                            save_project(project)
                            st.success(f"物品 {iname} 已更新")
                            st.rerun()

                    if st.button("删除物品", key=f"del_item_{item.id}", type="secondary"):
                        del project.items[item.id]
                        save_project(project)
                        st.success(f"物品 {item.name} 已删除")
                        st.rerun()

    with tab_add:
        with st.form("add_item"):
            iname = st.text_input("物品名称 *")
            idesc = st.text_area("描述")
            col1, col2 = st.columns(2)
            with col1:
                itype = st.selectbox("类型", ITEM_TYPE_OPTIONS, format_func=lambda x: ITEM_TYPE_LABELS.get(x, x))
                istatus = st.selectbox("状态", ITEM_STATUS_LIST, format_func=lambda s: ITEM_STATUS_LABELS.get(s.value, s.value))
            with col2:
                igrade = st.selectbox("品级", GRADE_OPTIONS, index=1, format_func=lambda x: GRADE_LABELS.get(x, x))
                char_options = {"": "（无）"}
                for cid, cchar in project.characters.items():
                    char_options[cid] = cchar.name
                iowner = st.selectbox("持有者", options=list(char_options.keys()), format_func=lambda x: char_options[x])
            ieffects = st.text_area("功效/能力")
            iorigin = st.text_input("来源/出处")
            loc_options = {"": "（无）"}
            for lid, lloc in project.locations.items():
                loc_options[lid] = lloc.name
            iloc = st.selectbox("所在地点", options=list(loc_options.keys()), format_func=lambda x: loc_options[x])
            itags = st.text_input("标签（逗号分隔）")
            inotes = st.text_area("备忘", height=40)
            if st.form_submit_button("添加") and iname:
                new_item = Item(
                    name=iname, description=idesc, item_type=itype, grade=igrade,
                    effects=ieffects, origin=iorigin,
                    owner_character_id=iowner if iowner else None,
                    location_id=iloc if iloc else None,
                    status=istatus,
                    tags=[t.strip() for t in itags.split(",") if t.strip()],
                    notes=inotes,
                )
                project.items[new_item.id] = new_item
                save_project(project)
                st.success(f"物品 {iname} 已添加")
                st.rerun()


# ---------- 页面：故事大纲 ----------
elif page == "故事大纲":
    st.header("故事大纲")

    tab_view_edit, tab_auto_gen, tab_continue, tab_import = st.tabs(["查看与编辑", "AI 全自动生成", "大纲续写", "导入/覆盖"])

    # ===== 辅助函数：扁平化大纲节点 =====
    def flatten_outline(node, depth=0):
        level_name = {0: "总纲", 1: "卷", 2: "幕", 3: "章"}.get(node.level, "")
        result = [(node.id, "　" * depth + f"[{level_name}] {node.title}", node)]
        for child in node.children:
            result.extend(flatten_outline(child, depth + 1))
        return result

    # ===== Tab 1: 查看与编辑 =====
    with tab_view_edit:
        if project.outline:
            st.subheader("当前大纲")
            def render_node(node, depth=0):
                indent = "　" * depth
                level_name = {0: "总纲", 1: "卷", 2: "幕", 3: "章"}.get(node.level, "")
                st.write(f"{indent}**[{level_name}] {node.title}** — {node.summary[:50]}...")
                for child in node.children:
                    render_node(child, depth + 1)
            render_node(project.outline)

            st.divider()
            st.subheader("大纲编辑")
            flat_nodes = flatten_outline(project.outline)
            node_options = {nid: label for nid, label, _ in flat_nodes}
            selected_node_id = st.selectbox(
                "选择要操作的节点",
                options=list(node_options.keys()),
                format_func=lambda x: node_options[x],
                key="outline_edit_select",
            )
            selected_node = next(n for nid, _, n in flat_nodes if nid == selected_node_id)

            # 修改节点
            with st.form("edit_node_form"):
                level_name = {0: "总纲", 1: "卷", 2: "幕", 3: "章"}.get(selected_node.level, "未知")
                st.caption(f"当前级别: {level_name}")
                edit_title = st.text_input("标题", value=selected_node.title, key=f"edit_title_{selected_node_id}")
                edit_summary = st.text_area("摘要", value=selected_node.summary, height=80, key=f"edit_summary_{selected_node_id}")
                if st.form_submit_button("保存修改"):
                    pipeline.update_outline_node(project, selected_node_id, title=edit_title, summary=edit_summary)
                    st.success("节点已更新")
                    st.rerun()

            # 添加子节点
            if selected_node.level >= 3:
                st.caption("章节点下不能再添加子节点")
            else:
                with st.form("add_child_form"):
                    child_title = st.text_input("子节点标题", key=f"child_title_{selected_node_id}")
                    child_summary = st.text_area("子节点摘要", height=60, key=f"child_summary_{selected_node_id}")
                    # 递进式级别选择：允许添加当前级别+1到3的任意级别
                    available_levels = list(range(selected_node.level + 1, 4))
                    level_labels = {1: "卷", 2: "幕", 3: "章"}
                    child_level = st.selectbox(
                        "添加级别",
                        available_levels,
                        format_func=lambda x: level_labels.get(x, "未知"),
                        index=0,
                        key=f"child_level_{selected_node_id}",
                    )
                    # 当添加章时，显示序号输入
                    child_seq = None
                    if child_level == 3:
                        next_seq = max((c.sequence_number for c in project.chapters.values()), default=0) + 1
                        child_seq = st.number_input("章节序号", min_value=1, value=next_seq, step=1, key=f"child_seq_{selected_node_id}")
                    parent_level_label = {0: "总纲", 1: "卷", 2: "幕", 3: "章"}.get(selected_node.level, "")
                    child_level_label = level_labels.get(child_level, "未知")
                    st.info(f"将在「{selected_node.title}」({parent_level_label}) 下添加 **{child_level_label}**")
                    if st.form_submit_button("添加子节点") and child_title.strip():
                        node = pipeline.add_outline_node(
                            project, parent_id=selected_node_id,
                            title=child_title.strip(), summary=child_summary, level=child_level,
                        )
                        # 如果是章且指定了序号，同步更新章节序号
                        if child_level == 3 and node.chapter_id and child_seq is not None:
                            ch = project.chapters.get(node.chapter_id)
                            if ch:
                                ch.sequence_number = int(child_seq)
                                save_project(project)
                        st.success("子节点已添加")
                        st.rerun()

            # 删除节点
            if selected_node_id != project.outline.id:
                if st.button("删除选中节点", type="secondary"):
                    pipeline.remove_outline_node(project, selected_node_id, remove_linked_chapter=True)
                    st.success("节点已删除")
                    st.rerun()
            else:
                st.caption("根节点不可删除，如需清空大纲请使用「导入/覆盖」功能。")
        else:
            st.info("尚未导入大纲，可在「导入/覆盖」标签页导入，或在大纲创建后在此编辑。")

        st.divider()
        st.subheader("章节列表")
        if project.chapters:
            st.write("已有章节:")
            for ch_item in sorted(project.chapters.values(), key=lambda c: c.sequence_number):
                with st.expander(f"第{ch_item.sequence_number}章 《{ch_item.title}》"):
                    with st.form(f"edit_chapter_{ch_item.id}"):
                        edit_title = st.text_input("章节标题", value=ch_item.title, key=f"edit_title_{ch_item.id}")
                        edit_summary = st.text_area("章节摘要", value=ch_item.outline_summary, height=60, key=f"edit_summary_{ch_item.id}")
                        col_save, col_del = st.columns([1, 1])
                        with col_save:
                            save_clicked = st.form_submit_button("保存修改")
                        with col_del:
                            del_clicked = st.form_submit_button("删除章节", type="secondary")

                        if save_clicked:
                            ch_item.title = edit_title.strip()
                            ch_item.outline_summary = edit_summary
                            save_project(project)
                            st.success("已保存")
                        elif del_clicked:
                            if ch_item.id in project.chapters:
                                del project.chapters[ch_item.id]
                                save_project(project)
                                st.success("章节已删除")
                                st.rerun()
        else:
            st.info("暂无章节，请在大纲编辑中通过「添加子节点」添加章级别节点，或导入含章的详细大纲。")

    # ===== Tab 2: AI 全自动生成 =====
    with tab_auto_gen:
        st.subheader("AI 全自动生成大纲")
        st.info("基于已设定的世界观、人物等信息，让 AI 一次性生成完整的「总纲-卷-幕-章」四级大纲结构。")

        if not project.world or not project.world.name:
            st.warning("请先在【世界观设定】中设定世界观，AI 需要世界观信息来构建合理的故事大纲。")
        elif not pipeline.generator:
            st.error("未配置 AI 模型，请在 config.yaml 中设置")
        else:
            with st.form("auto_gen_outline_form"):
                st.markdown("**生成参数**")
                col_v, col_a, col_c = st.columns(3)
                with col_v:
                    num_volumes = st.number_input("卷数", min_value=1, max_value=20, value=3, step=1)
                with col_a:
                    min_acts = st.number_input("每卷最少幕数", min_value=3, max_value=20, value=5, step=1)
                with col_c:
                    min_chapters = st.number_input("每幕最少章数", min_value=3, max_value=20, value=5, step=1)
                extra_guidance = st.text_area(
                    "额外创作指导（可选）",
                    height=80,
                    placeholder="如：故事风格偏暗黑、主角要经历三次大挫折、结局要开放式...",
                )

                st.markdown("**阶段性要求（可选，控制每卷的剧情/实力边界）**")
                st.caption("每行对应一卷的约束，AI 会严格限制每卷的内容范围。留空表示不做限制。")
                vol_requirements_text = st.text_area(
                    "各卷阶段性约束",
                    height=120,
                    placeholder="第1卷：主角实力到达练气期，加入宗门\n第2卷：主角突破筑基期，参加宗门大比\n第3卷：主角进入金丹期，外出历练",
                    key="vol_req_text",
                )
                vol_requirements = [line.strip() for line in vol_requirements_text.strip().splitlines() if line.strip()] if vol_requirements_text.strip() else []

                total_estimate = num_volumes * min_acts * min_chapters
                st.caption(f"预估生成: {num_volumes} 卷 × {min_acts}+ 幕 × {min_chapters}+ 章 ≈ 至少 {total_estimate} 章")

                if project.outline:
                    st.warning("⚠️ 当前已有大纲，全自动生成将覆盖现有大纲。已有的章节关联将被重建。")

                col_preview, col_gen = st.columns([1, 2])
                with col_preview:
                    preview_submitted = st.form_submit_button("预览提示词", use_container_width=True)
                with col_gen:
                    gen_submitted = st.form_submit_button("开始全自动生成", type="primary", use_container_width=True)

            if preview_submitted:
                st.session_state.auto_gen_preview = {
                    "num_volumes": int(num_volumes),
                    "min_acts_per_volume": int(min_acts),
                    "min_chapters_per_act": int(min_chapters),
                    "extra_guidance": extra_guidance,
                    "volume_requirements": vol_requirements if vol_requirements else None,
                }
                st.rerun()

            # 展示提示词预览
            if "auto_gen_preview" in st.session_state:
                st.divider()
                st.subheader("生成提示词预览")
                with st.spinner("正在构建提示词..."):
                    preview_prompt = pipeline.get_auto_generate_outline_prompt(
                        project,
                        **st.session_state.auto_gen_preview,
                    )
                st.code(preview_prompt, language="markdown")
                if st.button("关闭预览", key="close_preview"):
                    del st.session_state.auto_gen_preview
                    st.rerun()

            if gen_submitted:
                # 清除可能存在的预览
                if "auto_gen_preview" in st.session_state:
                    del st.session_state.auto_gen_preview
                st.subheader("生成进度")
                timer_placeholder = st.empty()
                status_placeholder = st.empty()
                stream_container = st.container()
                with stream_container:
                    stream_text_area = st.empty()

                start_time = time.time()
                # 使用可变容器，避免 nonlocal 在模块顶层不可用的问题
                state = {"full_text": "", "has_error": False, "error_msg": ""}

                def _update_timer():
                    elapsed = time.time() - start_time
                    mins, secs = divmod(int(elapsed), 60)
                    timer_placeholder.caption(f"⏱️ 已耗时: {mins:02d}:{secs:02d}")

                def _stream_callback(chunk: str):
                    if chunk.startswith("\n[生成错误:"):
                        state["has_error"] = True
                        state["error_msg"] = chunk.strip()
                        return
                    state["full_text"] += chunk
                    _update_timer()
                    # 实时显示已生成的文本（截取尾部避免过长）
                    display = state["full_text"]
                    if len(display) > 3000:
                        display = "...（前部内容已省略）...\n" + display[-3000:]
                    stream_text_area.code(display, language="json")

                status_placeholder.info("AI 正在构思完整的故事大纲（思考模式下可能需要数分钟）...")
                _update_timer()

                try:
                    outline = pipeline.auto_generate_outline(
                        project,
                        num_volumes=int(num_volumes),
                        min_acts_per_volume=int(min_acts),
                        min_chapters_per_act=int(min_chapters),
                        extra_guidance=extra_guidance,
                        volume_requirements=vol_requirements if vol_requirements else None,
                        stream_callback=_stream_callback,
                    )

                    if state["has_error"]:
                        raise RuntimeError(state["error_msg"])

                    elapsed = time.time() - start_time
                    mins, secs = divmod(int(elapsed), 60)
                    # 统计生成结果
                    vol_count = len([c for c in outline.children if c.level == 1])
                    act_count = sum(len([a for a in v.children if a.level == 2]) for v in outline.children if v.level == 1)
                    chap_count = len(outline.flatten_chapters())
                    status_placeholder.success(f"大纲生成完成！共 {vol_count} 卷 / {act_count} 幕 / {chap_count} 章（耗时 {mins:02d}:{secs:02d}）")
                    stream_text_area.empty()
                    st.rerun()
                except Exception as e:
                    elapsed = time.time() - start_time
                    mins, secs = divmod(int(elapsed), 60)
                    timer_placeholder.caption(f"⏱️ 总耗时: {mins:02d}:{secs:02d}")
                    status_placeholder.error(f"生成失败（耗时 {mins:02d}:{secs:02d}）: {e}")

            # 生成后展示当前大纲概要
            if project.outline and project.outline.children:
                st.divider()
                st.subheader("当前大纲概要")
                for vol in project.outline.children:
                    if vol.level == 1:
                        act_count = len([a for a in vol.children if a.level == 2])
                        chap_count = sum(len([c for c in a.children if c.level == 3]) for a in vol.children if a.level == 2)
                        with st.expander(f"📖 {vol.title}（{act_count} 幕 / {chap_count} 章）"):
                            st.markdown(f"**摘要**: {vol.summary}")
                            for act in vol.children:
                                if act.level == 2:
                                    ch_count = len([c for c in act.children if c.level == 3])
                                    st.markdown(f"&emsp;📜 **{act.title}**（{ch_count} 章）: {act.summary[:60]}...")
                                    for chap in act.children:
                                        if chap.level == 3:
                                            tone = f" [{chap.emotional_tone}]" if chap.emotional_tone else ""
                                            st.markdown(f"&emsp;&emsp;📄 {chap.title}{tone}: {chap.summary[:40]}...")

    # ===== Tab 3: 大纲续写 =====
    with tab_continue:
        st.subheader("大纲续写")
        st.info("基于已有大纲内容，让 AI 续写新的卷/幕/章。AI 会参考最近的 10 幕内容作为上下文，越靠后的幕权重越高。")

        if not project.outline or not project.outline.children:
            st.warning("当前没有大纲，请先使用【AI 全自动生成】创建初始大纲。")
        elif not pipeline.generator:
            st.error("未配置 AI 模型，请在 config.yaml 中设置")
        else:
            # 显示当前大纲规模
            existing_vols = [v for v in project.outline.children if v.level == 1]
            existing_acts = sum(len([a for a in v.children if a.level == 2]) for v in existing_vols)
            existing_chaps = len(project.outline.flatten_chapters())
            st.caption(f"当前大纲: {len(existing_vols)} 卷 / {existing_acts} 幕 / {existing_chaps} 章")

            with st.form("continue_outline_form"):
                st.markdown("**续写参数**")
                col_nv, col_a2, col_c2 = st.columns(3)
                with col_nv:
                    cont_num_volumes = st.number_input("续写卷数", min_value=1, max_value=10, value=1, step=1, key="cont_nvol")
                with col_a2:
                    cont_min_acts = st.number_input("每卷最少幕数", min_value=3, max_value=20, value=5, step=1, key="cont_nact")
                with col_c2:
                    cont_min_chapters = st.number_input("每幕最少章数", min_value=3, max_value=20, value=5, step=1, key="cont_nchap")
                cont_extra_guidance = st.text_area(
                    "额外创作指导（可选）",
                    height=80,
                    placeholder="如：本卷要揭开反派身份、主角觉醒新能力...",
                    key="cont_guidance",
                )

                next_vol_num = len(existing_vols) + 1

                st.markdown("**阶段性要求（可选，控制每卷的剧情/实力边界）**")
                st.caption("每行对应续写一卷的约束，AI 会严格限制每卷的内容范围。留空表示不做限制。")
                cont_vol_req_text = st.text_area(
                    "各卷阶段性约束",
                    height=120,
                    placeholder=f"第{next_vol_num}卷：主角实力到达XX境界\n第{next_vol_num+1}卷：主角完成XX任务",
                    key="cont_vol_req_text",
                )
                cont_vol_requirements = [line.strip() for line in cont_vol_req_text.strip().splitlines() if line.strip()] if cont_vol_req_text.strip() else []

                est_new_chaps = cont_num_volumes * cont_min_acts * cont_min_chapters
                st.caption(f"将从第 {next_vol_num} 卷开始续写，预估新增 ≈ {est_new_chaps} 章")

                cont_submitted = st.form_submit_button("开始续写大纲", type="primary", use_container_width=True)

            if cont_submitted:
                st.subheader("续写进度")
                cont_timer_ph = st.empty()
                cont_status_ph = st.empty()
                cont_stream_container = st.container()
                with cont_stream_container:
                    cont_stream_area = st.empty()

                cont_start_time = time.time()
                cont_state = {"full_text": "", "has_error": False, "error_msg": ""}

                def _cont_update_timer():
                    elapsed = time.time() - cont_start_time
                    mins, secs = divmod(int(elapsed), 60)
                    cont_timer_ph.caption(f"⏱️ 已耗时: {mins:02d}:{secs:02d}")

                def _cont_stream_callback(chunk: str):
                    if chunk.startswith("\n[生成错误:"):
                        cont_state["has_error"] = True
                        cont_state["error_msg"] = chunk.strip()
                        return
                    cont_state["full_text"] += chunk
                    _cont_update_timer()
                    display = cont_state["full_text"]
                    if len(display) > 3000:
                        display = "...（前部内容已省略）...\n" + display[-3000:]
                    cont_stream_area.code(display, language="json")

                cont_status_ph.info("AI 正在续写大纲（思考模式下可能需要数分钟）...")
                _cont_update_timer()

                try:
                    added_count = pipeline.continue_outline(
                        project,
                        num_new_volumes=int(cont_num_volumes),
                        min_acts_per_volume=int(cont_min_acts),
                        min_chapters_per_act=int(cont_min_chapters),
                        extra_guidance=cont_extra_guidance,
                        volume_requirements=cont_vol_requirements if cont_vol_requirements else None,
                        stream_callback=_cont_stream_callback,
                    )

                    if cont_state["has_error"]:
                        raise RuntimeError(cont_state["error_msg"])

                    elapsed = time.time() - cont_start_time
                    mins, secs = divmod(int(elapsed), 60)
                    # 统计续写后总量
                    total_vols = len([v for v in project.outline.children if v.level == 1])
                    total_chaps = len(project.outline.flatten_chapters())
                    cont_status_ph.success(
                        f"续写完成！新增 {added_count} 卷（当前共 {total_vols} 卷 / {total_chaps} 章，耗时 {mins:02d}:{secs:02d}）"
                    )
                    cont_stream_area.empty()
                    st.rerun()
                except Exception as e:
                    elapsed = time.time() - cont_start_time
                    mins, secs = divmod(int(elapsed), 60)
                    cont_timer_ph.caption(f"⏱️ 总耗时: {mins:02d}:{secs:02d}")
                    cont_status_ph.error(f"续写失败（耗时 {mins:02d}:{secs:02d}）: {e}")

            # 续写后展示当前大纲概要
            if project.outline and project.outline.children:
                st.divider()
                st.subheader("当前大纲概要")
                for vol in project.outline.children:
                    if vol.level == 1:
                        act_count = len([a for a in vol.children if a.level == 2])
                        chap_count = sum(len([c for c in a.children if c.level == 3]) for a in vol.children if a.level == 2)
                        with st.expander(f"📖 {vol.title}（{act_count} 幕 / {chap_count} 章）"):
                            st.markdown(f"**摘要**: {vol.summary}")
                            for act in vol.children:
                                if act.level == 2:
                                    ch_count = len([c for c in act.children if c.level == 3])
                                    st.markdown(f"&emsp;📜 **{act.title}**（{ch_count} 章）: {act.summary[:60]}...")

    # ===== Tab 4: 导入/覆盖 =====
    with tab_import:
        st.info("上传 JSON 文件将完全覆盖现有大纲。如需保留当前大纲，请先导出备份。")
        with st.expander("查看 JSON 格式示例"):
            st.code(json.dumps({
                "title": "全书总纲",
                "level": 0,
                "summary": "总纲摘要",
                "children": [
                    {
                        "title": "第一卷：暗流",
                        "level": 1,
                        "summary": "卷摘要",
                        "children": [
                            {
                                "title": "第一幕：开端",
                                "level": 2,
                                "summary": "幕摘要",
                                "children": [
                                    {
                                        "title": "第一章：开端",
                                        "level": 3,
                                        "summary": "章节摘要",
                                        "plot_points": ["情节点1", "情节点2"],
                                        "characters_involved": [],
                                        "emotional_tone": "紧张"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }, ensure_ascii=False, indent=2), language="json")

        uploaded = st.file_uploader("上传大纲 JSON", type=["json"])
        if uploaded is not None:
            data = json.load(uploaded)
            outline = OutlineNode.from_dict(data)
            pipeline.set_outline(project, outline)
            st.success(f"大纲已导入，共 {len(outline.flatten_chapters())} 章")
            st.rerun()


# ---------- 页面：伏笔设计 ----------
elif page == "伏笔设计":
    st.header("伏笔设计")
    tab_manage, tab_bind = st.tabs(["伏笔库", "绑定章节"])

    with tab_manage:
        with st.form("add_foreshadowing"):
            st.subheader("新增伏笔")
            fs_name = st.text_input("伏笔名称/代号")
            fs_desc = st.text_area("伏笔描述（读者最终看到的是什么）")
            fs_hint = st.text_area("埋设提示（可选，告诉AI如何暗示）")
            fs_importance = st.selectbox("重要性", ["minor", "medium", "major", "critical"])
            if st.form_submit_button("添加") and fs_name:
                fs = pipeline.add_foreshadowing(
                    project, name=fs_name, description=fs_desc,
                    hint_text=fs_hint, importance=fs_importance,
                )
                st.success(f"伏笔 {fs.name} 已添加")
                st.rerun()

        st.divider()
        st.subheader("伏笔列表")
        if not project.foreshadowings:
            st.info("暂无伏笔")
        for fs in project.foreshadowings.values():
            status_emoji = {"planned": "📝", "seeded": "🌱", "resolved": "✅", "abandoned": "❌"}.get(fs.status.value, "📝")
            with st.expander(f"{status_emoji} [{fs.importance.upper()}] {fs.name} ({fs.status.value})"):
                st.write(f"**描述**: {fs.description}")
                if fs.hint_text:
                    st.write(f"**埋设提示**: {fs.hint_text}")
                st.write(f"**埋设章节**: {fs.seed_chapter_id or '未分配'}")
                st.write(f"**回收章节**: {fs.resolve_chapter_id or '未分配'}")

    with tab_bind:
        if not project.foreshadowings:
            st.info("请先添加伏笔")
        elif not project.chapters:
            st.info("请先导入大纲生成章节")
        else:
            st.subheader("将伏笔绑定到章节")
            chapter_options = {ch.id: f"第{ch.sequence_number}章 《{ch.title}》" for ch in sorted(project.chapters.values(), key=lambda c: c.sequence_number)}
            col_fs, col_ch, col_action = st.columns([2, 2, 1])
            with col_fs:
                fs_id = st.selectbox("选择伏笔", options=list(project.foreshadowings.keys()), format_func=lambda x: project.foreshadowings[x].name)
            with col_ch:
                ch_id = st.selectbox("选择章节", options=list(chapter_options.keys()), format_func=lambda x: chapter_options[x])
            with col_action:
                action = st.selectbox("操作", ["seed", "resolve"], format_func=lambda x: "埋设" if x == "seed" else "回收")
                if st.button("绑定", type="primary"):
                    pipeline.bind_foreshadowing_to_chapter(project, fs_id, ch_id, action)
                    st.success("绑定成功")
                    st.rerun()

            st.divider()
            st.subheader("各章节伏笔一览")
            for ch in sorted(project.chapters.values(), key=lambda c: c.sequence_number):
                seeded = [project.foreshadowings.get(fid) for fid in ch.foreshadowing_seeded]
                resolved = [project.foreshadowings.get(fid) for fid in ch.foreshadowing_resolved]
                if seeded or resolved:
                    with st.expander(f"第{ch.sequence_number}章 《{ch.title}》"):
                        if seeded:
                            st.write("🌱 埋设:")
                            for fs in seeded:
                                if fs:
                                    st.write(f"  - {fs.name}")
                        if resolved:
                            st.write("✅ 回收:")
                            for fs in resolved:
                                if fs:
                                    st.write(f"  - {fs.name}")


# ---------- 页面：风格设定 ----------
elif page == "风格设定":
    st.header("风格设定")
    tab_basic, tab_mimicry = st.tabs(["基础风格", "文笔模仿"])

    with tab_basic:
        style = project.style
        with st.form("style_form"):
            perspective = st.selectbox("叙事视角", ["first_person", "third_person_limited", "third_person_omniscient"], index=["first_person", "third_person_limited", "third_person_omniscient"].index(style.narrative_perspective) if style.narrative_perspective in ["first_person", "third_person_limited", "third_person_omniscient"] else 1)
            tense = st.selectbox("时态", ["past", "present"], index=0 if style.tense == "past" else 1)
            tone = st.text_input("整体语调", value=style.tone)
            vocabulary = st.text_input("词汇风格", value=style.vocabulary_level, placeholder="古雅 / 通俗 / 华丽 / 冷峻...")
            density = st.select_slider("描写密度", options=["sparse", "balanced", "dense"], value=style.description_density or "balanced")
            banned = st.text_area("禁用词（逗号分隔）", value=", ".join(style.banned_words))
            sample = st.text_area("参考段落样例", value=style.sample_paragraph, height=150)
            if st.form_submit_button("保存"):
                style.narrative_perspective = perspective
                style.tense = tense
                style.tone = tone
                style.vocabulary_level = vocabulary
                style.description_density = density
                style.banned_words = [w.strip() for w in banned.split(",") if w.strip()]
                style.sample_paragraph = sample
                project.style = style
                save_project(project)
                st.success("风格设定已保存")

    with tab_mimicry:
        st.subheader("文笔模仿")
        mimicry_enabled = st.toggle("启用文笔模仿模式", value=project.style.mimicry_mode)
        if mimicry_enabled != project.style.mimicry_mode:
            project.style.mimicry_mode = mimicry_enabled
            save_project(project)
            st.rerun()

        if mimicry_enabled:
            target_author = st.text_input("目标模仿作者", value=project.style.reference_author, placeholder="如：金庸、古龙、刘慈欣...")
            if target_author != project.style.reference_author:
                project.style.reference_author = target_author
                save_project(project)

            st.divider()
            st.subheader("风格参考库")
            with st.form("add_style_ref"):
                ref_name = st.text_input("参考名称")
                ref_author = st.text_input("参考作者")
                ref_desc = st.text_area("风格描述")
                ref_samples = st.text_area("参考文本片段（可多条，空行分隔）", height=100)
                if st.form_submit_button("添加") and ref_name:
                    texts = [t.strip() for t in ref_samples.split("\n\n") if t.strip()]
                    pipeline.add_style_reference(
                        project, name=ref_name, reference_author=ref_author,
                        description=ref_desc, sample_texts=texts, is_active=True,
                    )
                    st.success("风格参考已添加")
                    st.rerun()

            for ref in project.style_references.values():
                active = st.checkbox(f"【{ref.name}】{ref.reference_author}", value=ref.is_active, key=f"ref_{ref.id}")
                if active != ref.is_active:
                    ref.is_active = active
                    save_project(project)
                    st.rerun()
                with st.expander("详情"):
                    st.write(f"描述: {ref.description}")
                    if ref.sample_texts:
                        st.text_area("参考片段", value=ref.sample_texts[0][:500], height=80, disabled=True)
                    if ref.analyzed_traits:
                        st.write(f"AI分析特征: {', '.join(ref.analyzed_traits)}")
                    if pipeline.generator and ref.sample_texts:
                        if st.button("AI分析风格", key=f"analyze_{ref.id}"):
                            with st.spinner("分析中..."):
                                pipeline.analyze_style_from_text(project, ref.id, ref.sample_texts[0])
                            st.success("分析完成")
                            st.rerun()


# ---------- 页面：章节创作（核心） ----------
elif page == "章节创作":
    st.header("章节创作")

    if not project.chapters:
        st.warning("暂无章节，请先在【故事大纲】中添加章节或导入含章的详细大纲")
        st.stop()

    # 章节选择 — 使用 session_state 记住当前章节，避免 rerun 后跳回第一章
    if "selected_chapter_id" not in st.session_state:
        st.session_state.selected_chapter_id = None

    chapter_list = sorted(project.chapters.values(), key=lambda c: c.sequence_number)
    chapter_ids = [c.id for c in chapter_list]

    # 确保选中的章节在当前列表中
    if st.session_state.selected_chapter_id not in chapter_ids:
        st.session_state.selected_chapter_id = chapter_list[0].id

    selected_index = chapter_ids.index(st.session_state.selected_chapter_id)

    selected_chapter = st.selectbox(
        "选择章节",
        options=chapter_list,
        index=selected_index,
        format_func=lambda ch: f"第{ch.sequence_number}章 《{ch.title}》 [{ch.status.value}]",
    )

    # 用户切换章节时更新 session_state 并清除生成缓存
    if selected_chapter.id != st.session_state.selected_chapter_id:
        # 清除旧章节的编辑器 widget 状态
        old_editor_key = f"chapter_content_editor_{st.session_state.selected_chapter_id}"
        st.session_state.pop(old_editor_key, None)
        st.session_state.selected_chapter_id = selected_chapter.id
        st.session_state.generation_text = ""
        st.rerun()

    ch = selected_chapter

    # ========== 幕选择（上下文定位）==========
    def _collect_acts(node: OutlineNode) -> list:
        """递归收集所有幕节点（level=2）"""
        acts = []
        if node.level == 2:
            acts.append(node)
        for child in node.children:
            acts.extend(_collect_acts(child))
        return acts

    selected_act = None
    selected_volume_summary = ""
    selected_act_summary = ""
    default_act_id = None
    is_manual_override = False

    if project.outline:
        all_acts = _collect_acts(project.outline)
        if all_acts:
            # 查找当前章节默认关联的幕
            if ch.id:
                for chapter_node in project.outline.flatten_chapters():
                    if chapter_node.chapter_id == ch.id:
                        path_nodes = project._trace_outline_path_nodes(chapter_node)
                        for pn in path_nodes:
                            if pn.level == 2:
                                default_act_id = pn.id
                                break
                        break

            act_options = {act.id: act.title for act in all_acts}
            default_index = 0
            if default_act_id and default_act_id in act_options:
                default_index = list(act_options.keys()).index(default_act_id)

            selected_act_id = st.selectbox(
                "选择幕（上下文）",
                options=list(act_options.keys()),
                index=default_index,
                format_func=lambda x: act_options[x],
                key=f"chapter_act_select_{ch.id}",
            )

            # 判断是否用户手动覆盖了默认关联
            is_manual_override = (default_act_id is not None and selected_act_id != default_act_id) or (default_act_id is None)

            selected_act = next((a for a in all_acts if a.id == selected_act_id), None)
            if selected_act:
                selected_act_summary = selected_act.summary
                # 查找所属卷摘要
                path_nodes = project._trace_outline_path_nodes(selected_act)
                for pn in path_nodes:
                    if pn.level == 1:
                        selected_volume_summary = pn.summary
                        break

                col_act, col_vol = st.columns(2)
                with col_act:
                    st.markdown("**📜 幕摘要**（高影响力）")
                    st.info(selected_act_summary or "暂无摘要")
                with col_vol:
                    st.markdown("**📖 卷摘要**（参考影响）")
                    st.info(selected_volume_summary or "暂无摘要")

    st.divider()

    # 三栏布局：情节流程 | 伏笔绑定 | 生成与预览
    col_left, col_mid, col_right = st.columns([2, 1.5, 2.5])

    with col_left:
        st.subheader("📋 情节流程")
        # 从 notes 中解析已保存的情感基调和情节点
        _emotional_tone_default = ""
        _plot_points_default = ""
        if ch.notes:
            _in_plot = False
            for _line in ch.notes.splitlines():
                if _line.startswith("情感基调:"):
                    _emotional_tone_default = _line.split(":", 1)[1].strip()
                elif _line.startswith("情节点:"):
                    _in_plot = True
                elif _in_plot:
                    _plot_points_default += _line + "\n"
            _plot_points_default = _plot_points_default.strip()

        # 如果从 notes 没解析到，尝试从大纲节点读取（JSON 导入的大纲数据）
        if not _emotional_tone_default or not _plot_points_default:
            if project.outline:
                for node in project.outline.flatten_chapters():
                    if node.chapter_id == ch.id or node.title == ch.title:
                        if not _emotional_tone_default:
                            _emotional_tone_default = node.emotional_tone or ""
                        if not _plot_points_default and node.plot_points:
                            _plot_points_default = "\n".join(node.plot_points)
                        break

        with st.form("chapter_plan"):
            summary = st.text_area("本章摘要", value=ch.outline_summary, height=80)
            plot_points = st.text_area("情节点（每行一个）", value=_plot_points_default, height=100)
            emotional_tone = st.text_input("情感基调", value=_emotional_tone_default)
            if st.form_submit_button("保存"):
                # 直接通过 project.chapters 修改，避免引用不一致问题
                target_ch = project.chapters.get(ch.id)
                if target_ch:
                    target_ch.outline_summary = summary
                    target_ch.notes = f"情感基调: {emotional_tone}\n情节点:\n{plot_points}"
                    # 同步更新对应的大纲节点
                    if project.outline:
                        for node in project.outline.flatten_chapters():
                            if node.chapter_id == ch.id or node.title == target_ch.title:
                                node.summary = summary
                                node.emotional_tone = emotional_tone
                                node.plot_points = [p.strip() for p in plot_points.splitlines() if p.strip()]
                                break
                    save_project(project)
                    st.success("已保存")
                else:
                    st.error("章节对象异常，请刷新页面重试")

        st.subheader("🎭 出场人物")
        char_options = {cid: project.characters[cid].name for cid in project.characters}
        selected_chars = st.multiselect(
            "选择出场人物",
            options=list(char_options.keys()),
            default=ch.characters_present,
            format_func=lambda x: char_options.get(x, x),
        )
        if st.button("更新出场人物"):
            target_ch = project.chapters.get(ch.id)
            if target_ch:
                target_ch.characters_present = selected_chars
                # 同步更新对应的大纲节点
                if project.outline:
                    for node in project.outline.flatten_chapters():
                        if node.chapter_id == ch.id or node.title == target_ch.title:
                            node.characters_involved = selected_chars
                            break
                save_project(project)
                st.success("已更新")
            else:
                st.error("章节对象异常，请刷新页面重试")

        # 剧情记忆展示
        st.subheader("🧠 剧情记忆")
        if ch.plot_memory:
            st.info(ch.plot_memory)
        else:
            st.caption("点击「审校通过」后，AI 会自动分析本章内容并生成剧情记忆。")

    with col_mid:
        st.subheader("🌱 伏笔绑定")
        available_fs = {fid: fs for fid, fs in project.foreshadowings.items() if fs.status != ForeshadowingStatus.RESOLVED}
        if available_fs:
            to_seed = st.multiselect(
                "本章埋设",
                options=list(available_fs.keys()),
                default=ch.foreshadowing_seeded,
                format_func=lambda x: f"{available_fs[x].name} ({available_fs[x].status.value})",
            )
            to_resolve = st.multiselect(
                "本章回收",
                options=[fid for fid, fs in available_fs.items() if fs.status == ForeshadowingStatus.SEEDED],
                default=ch.foreshadowing_resolved,
                format_func=lambda x: available_fs[x].name,
            )
            if st.button("更新伏笔绑定"):
                ch.foreshadowing_seeded = to_seed
                ch.foreshadowing_resolved = to_resolve
                save_project(project)
                st.success("已更新")
        else:
            st.info("暂无可用伏笔，请在【伏笔设计】中添加")

        st.subheader("🎨 当前风格")
        st.write(f"视角: {project.style.narrative_perspective}")
        st.write(f"语调: {project.style.tone or '默认'}")
        st.write(f"词汇: {project.style.vocabulary_level or '默认'}")
        if project.style.mimicry_mode:
            st.write(f"✨ 模仿: {project.style.reference_author}")

        # ========== 分支剧情管理 ==========
        st.subheader("🌿 分支剧情")

        # 手动添加分支
        with st.expander("➕ 手动添加分支", expanded=False):
            with st.form("add_branch_form"):
                branch_title = st.text_input("分支名称")
                branch_desc = st.text_area("分支描述/触发事件")
                branch_importance = st.selectbox("重要性", ["minor", "medium", "major"], index=1)
                if st.form_submit_button("添加") and branch_title:
                    new_branch = BranchPlot(
                        title=branch_title,
                        description=branch_desc,
                        importance=branch_importance,
                        origin_chapter_id=ch.id,
                        status=BranchStatus.OPEN,
                    )
                    project.branch_plots[new_branch.id] = new_branch
                    save_project(project)
                    st.success(f"已添加分支: {branch_title}")
                    st.rerun()

        # 展示活跃分支
        active_branches = [
            b for b in project.branch_plots.values()
            if b.status in (BranchStatus.OPEN, BranchStatus.IN_PROGRESS)
        ]
        if active_branches:
            st.caption(f"当前活跃分支: {len(active_branches)} 个")
            for branch in active_branches:
                with st.container(border=True):
                    st.markdown(f"**{branch.title}** `[{branch.importance}]`")
                    st.caption(branch.description or "暂无描述")
                    # 状态选择
                    new_status = st.selectbox(
                        "状态",
                        [BranchStatus.OPEN, BranchStatus.IN_PROGRESS, BranchStatus.RESOLVED, BranchStatus.ABANDONED],
                        index=[BranchStatus.OPEN, BranchStatus.IN_PROGRESS, BranchStatus.RESOLVED, BranchStatus.ABANDONED].index(branch.status),
                        format_func=lambda s: {"open": "🟡 待推进", "in_progress": "🟢 推进中", "resolved": "✅ 已收束", "abandoned": "⚪ 已废弃"}.get(s.value, s.value),
                        key=f"branch_status_{branch.id}_{ch.id}",
                    )
                    if new_status != branch.status:
                        branch.status = new_status
                        branch.updated_at = datetime.now().isoformat()
                        save_project(project)
                        st.rerun()
                    # 标记本章是否推进了该分支
                    is_progressed = ch.id in branch.progress_chapter_ids
                    if st.checkbox("本章推进了该分支", value=is_progressed, key=f"branch_prog_{branch.id}_{ch.id}"):
                        if ch.id not in branch.progress_chapter_ids:
                            branch.progress_chapter_ids.append(ch.id)
                            branch.status = BranchStatus.IN_PROGRESS
                            branch.updated_at = datetime.now().isoformat()
                            save_project(project)
                            st.rerun()
                    else:
                        if ch.id in branch.progress_chapter_ids:
                            branch.progress_chapter_ids.remove(ch.id)
                            branch.updated_at = datetime.now().isoformat()
                            save_project(project)
                            st.rerun()
        else:
            st.info("暂无活跃分支。AI 审校时自动识别，或手动添加。")

    with col_right:
        # ---- 防重复点击状态管理 ----
        if "processing_action" not in st.session_state:
            st.session_state.processing_action = None
        is_processing = st.session_state.processing_action is not None

        st.subheader("🤖 内容生成")
        if not pipeline.generator:
            st.error("未配置 AI 模型，请在 config.yaml 中设置")
        else:
            gen_cols = st.columns([1, 1])
            temperature = gen_cols[0].slider("温度", 0.0, 1.0, 0.7, 0.05, disabled=is_processing)
            max_tokens = gen_cols[1].number_input("最大Token", 1000, 8000, 7000, 4000, disabled=is_processing)

            if st.button("生成章节", type="primary", use_container_width=True, disabled=is_processing):
                st.session_state.processing_action = "generate"
                st.session_state.generation_text = ""
                st.session_state._gen_buffer = ""
                st.rerun()

            # ---- 执行：生成章节 ----
            if st.session_state.processing_action == "generate":
                # 生成前检查必要字段
                if not ch.outline_summary:
                    st.warning("⚠️ 本章摘要为空，AI 可能无法按预期生成内容。请在左侧「情节流程」中填写并保存。")
                if not ch.characters_present:
                    st.warning("⚠️ 未选择出场人物，AI 可能自行编造角色。请在左侧「出场人物」中选择并更新。")

                placeholder = st.empty()

                def on_chunk(chunk: str):
                    st.session_state._gen_buffer += chunk
                    placeholder.markdown(st.session_state._gen_buffer)

                # 如果用户手动切换了幕，将选定幕/卷摘要作为额外约束
                extra_constraints = []
                if is_manual_override and selected_act_summary:
                    extra_constraints.append(
                        f"【当前幕要求 — 重要指导（用户指定）】{selected_act_summary}"
                    )
                if is_manual_override and selected_volume_summary:
                    extra_constraints.append(
                        f"【所属卷背景（用户指定）】{selected_volume_summary}"
                    )

                with st.spinner("生成中..."):
                    try:
                        pipeline.generate_chapter(
                            project, ch.id,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream_callback=on_chunk,
                            extra_constraints=extra_constraints if extra_constraints else None,
                        )
                        st.session_state.generation_text = st.session_state._gen_buffer
                    except Exception as e:
                        st.error(f"生成失败: {e}")
                    finally:
                        st.session_state[f"_content_sync_{ch.id}"] = True
                        st.session_state.processing_action = None
                        st.rerun()

        # --- 修订重写区域 ---
        st.divider()
        st.subheader("🔄 修订重写")
        if ch.content and ch.content.strip():
            st.caption("基于已有正文，按你的修改意见让 AI 修订细节，保留整体结构。")
            revision_notes = st.text_area(
                "修改意见",
                height=120,
                placeholder="例如：\n- 第二段的战斗描写太平淡，增加更多动作细节和紧张感\n- 把主角的语气从犹豫改为坚定\n- 结尾的转折太突兀，增加一些铺垫",
                key="revision_notes",
                disabled=is_processing,
            )
            if st.button("修订重写", type="secondary", use_container_width=True, disabled=is_processing):
                if not revision_notes or not revision_notes.strip():
                    st.warning("请输入修改意见")
                    st.session_state.processing_action = None
                else:
                    st.session_state.processing_action = "revise"
                    st.session_state.generation_text = ""
                    st.session_state._gen_buffer = ""
                    st.rerun()

            # ---- 执行：修订重写 ----
            if st.session_state.processing_action == "revise":
                rev_placeholder = st.empty()

                def on_rev_chunk(chunk: str):
                    st.session_state._gen_buffer += chunk
                    rev_placeholder.markdown(st.session_state._gen_buffer)

                with st.spinner("修订中..."):
                    try:
                        pipeline.revise_chapter(
                            project, ch.id,
                            revision_notes=revision_notes,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream_callback=on_rev_chunk,
                        )
                        st.session_state.generation_text = st.session_state._gen_buffer
                        st.success("修订完成")
                    except Exception as e:
                        st.error(f"修订失败: {e}")
                    finally:
                        st.session_state[f"_content_sync_{ch.id}"] = True
                        st.session_state.processing_action = None
                        st.rerun()
        else:
            st.info("章节正文为空，请先生成章节内容后再进行修订。")

        st.divider()
        st.subheader("✏️ 内容编辑")
        # 编辑器状态管理：使用 widget key + 条件 value 避免
        # Streamlit "default value + session_state" 冲突警告
        editor_key = f"chapter_content_editor_{ch.id}"
        # 生成/修订完成后，清除旧 widget 状态，让 value 参数重新生效
        if st.session_state.pop(f"_content_sync_{ch.id}", False):
            st.session_state.pop(editor_key, None)
        # key 不存在于 session_state 时需要通过 value 设置初始内容
        # key 已存在时 widget 自动从 session_state 读取，无需设 value
        if editor_key not in st.session_state:
            content_editor = st.text_area(
                "章节正文",
                value=ch.content or st.session_state.generation_text or "",
                key=editor_key,
                height=400,
                disabled=is_processing,
            )
        else:
            content_editor = st.text_area(
                "章节正文",
                key=editor_key,
                height=400,
                disabled=is_processing,
            )
        save_cols = st.columns([1, 1])
        if save_cols[0].button("保存正文", use_container_width=True, disabled=is_processing):
            # 直接通过 project.chapters 修改，避免 st.selectbox 返回对象与原始对象引用不一致
            target_ch = project.chapters.get(ch.id)
            if target_ch:
                target_ch.content = content_editor
                target_ch.word_count = count_chinese_words(target_ch.content)
                if target_ch.status == ChapterStatus.PLANNED:
                    target_ch.status = ChapterStatus.REVIEW
                save_project(project)
                st.success(f"已保存，{target_ch.word_count} 字")
                st.rerun()
            else:
                st.error("章节对象异常，请刷新页面重试")

        if save_cols[1].button("审校通过", use_container_width=True, disabled=is_processing):
            st.session_state.processing_action = "approve"
            st.rerun()

        # ---- 执行：审校通过 ----
        if st.session_state.processing_action == "approve":
            # 先AI分析章节内容，提取剧情记忆、新人物、新地点、新势力、分支剧情
            with st.spinner("正在分析章节内容..."):
                try:
                    analysis = pipeline.analyze_chapter(project, ch.id)
                    summary = pipeline.apply_chapter_analysis(project, ch.id, analysis)
                    # 显示分析结果
                    if summary["plot_memory_saved"]:
                        st.info(f"📖 已提取剧情记忆（{len(ch.plot_memory)}字）")
                    if summary["new_chars_added"] > 0:
                        st.info(f"👤 自动发现 {summary['new_chars_added']} 个新人物，已添加到人物设定")
                    if summary["new_locs_added"] > 0:
                        st.info(f"📍 自动发现 {summary['new_locs_added']} 个新地点，已添加到地点管理")
                    if summary.get("new_factions_added", 0) > 0:
                        st.info(f"🏛️ 自动发现 {summary['new_factions_added']} 个新势力，已添加到势力管理")
                    if summary.get("faction_bindings", 0) > 0:
                        st.info(f"🔗 自动绑定 {summary['faction_bindings']} 个人物势力关系")
                    if summary.get("new_items_added", 0) > 0:
                        st.info(f"📦 自动发现 {summary['new_items_added']} 个新物品，已添加到物品定义")
                    if summary.get("new_branches_added", 0) > 0:
                        st.info(f"🌿 自动发现 {summary['new_branches_added']} 个新分支剧情，已添加到分支列表")
                except Exception as e:
                    st.warning(f"章节分析失败（不影响审校）: {e}")

            pipeline.approve_chapter(project, ch.id)
            st.success("章节已标记为完成")
            st.session_state.processing_action = None
            # 保持当前章节，不要跳回第一章
            st.rerun()

    # 提示词与 Skill 展示
    st.divider()
    with st.expander("🔍 查看 AI 提示词与使用的 Skill", expanded=False):
        try:
            prompt_info = pipeline.prompt_builder.get_chapter_prompt_info(project, ch.id)

            st.subheader("🛠️ 使用的 Skill")
            if prompt_info["skills"]:
                skill_cols = st.columns(3)
                for idx, s in enumerate(prompt_info["skills"]):
                    with skill_cols[idx % 3]:
                        st.markdown(f"**{s['label']}**")
                        st.caption(f"`{s['name']}`")
                        if s.get("description"):
                            st.write(s["description"])
            else:
                st.info("未使用任何 Skill（将使用默认提示词片段）")

            st.subheader("📝 完整提示词")
            st.code(prompt_info["prompt"], language="markdown")
        except Exception as e:
            st.error(f"获取提示词信息失败: {e}")


# ---------- 页面：导出小说 ----------
elif page == "导出小说":
    st.header("导出小说")
    fmt = st.radio("格式", ["txt", "md"], horizontal=True)
    if st.button("导出全文", type="primary"):
        path = pipeline.export_project(project, format=fmt)
        st.success(f"已导出: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        st.download_button(
            label="下载文件",
            data=content,
            file_name=Path(path).name,
            mime="text/plain" if fmt == "txt" else "text/markdown",
        )
