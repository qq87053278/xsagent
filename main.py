#!/usr/bin/env python3
"""
XSAgent — AI 辅助小说创作系统
命令行入口

用法示例:
  python main.py init --title "我的小说" --author "作者名"
  python main.py list
  python main.py status --project <项目ID>
  python main.py character add --project <项目ID> --name "张三" --role protagonist
  python main.py world set --project <项目ID> --file world.json
  python main.py outline import --project <项目ID> --file outline.json
  python main.py generate chapter --project <项目ID> --seq 1
  python main.py export --project <项目ID> --format txt
"""

import sys
import json
import argparse
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent))

from xsagent.core.models import (
    NovelProject, Character, WorldBuilding, OutlineNode,
    StyleGuide, CharacterRole
)
from xsagent.storage.json_storage import JSONStorage
from xsagent.skills.skill_registry import SkillRegistry
from xsagent.generator.base import GeneratorFactory
from xsagent.workflow.pipeline import CreationPipeline
from xsagent.utils.config_loader import load_config


def _load_project(storage: JSONStorage, project_id: str) -> NovelProject:
    project = storage.load(project_id)
    if not project:
        print(f"错误: 项目不存在: {project_id}")
        sys.exit(1)
    return project


def _save_project(storage: JSONStorage, project: NovelProject) -> None:
    storage.save(project)
    print(f"项目已保存: {project.id}")


def cmd_init(args, pipeline: CreationPipeline, storage: JSONStorage):
    """初始化新项目"""
    project = pipeline.initialize_project(
        title=args.title,
        author=args.author or "",
        description=args.description or "",
    )
    print(f"项目已创建:")
    print(f"  ID:    {project.id}")
    print(f"  标题:  {project.title}")
    print(f"  作者:  {project.author}")
    print(f"  路径:  projects/{project.id}/")


def cmd_list(args, pipeline: CreationPipeline, storage: JSONStorage):
    """列出所有项目"""
    projects = storage.list_projects()
    if not projects:
        print("暂无项目")
        return
    print(f"{'ID':<12} {'标题':<20} {'作者':<10}")
    print("-" * 50)
    for pid in projects:
        p = storage.load(pid)
        if p:
            print(f"{p.id:<12} {p.title:<20} {p.author:<10}")


def cmd_status(args, pipeline: CreationPipeline, storage: JSONStorage):
    """查看项目状态"""
    project = _load_project(storage, args.project)
    stats = pipeline.get_project_stats(project)
    print(f"项目: {stats['project_title']} ({project.id})")
    print(f"  作者:        {project.author or '未设定'}")
    print(f"  世界观:      {stats['world_name']}")
    print(f"  人物数:      {stats['character_count']}")
    print(f"  总章节:      {stats['total_chapters']}")
    print(f"  已完成:      {stats['completed_chapters']}")
    print(f"  总字数:      {stats['total_words']}")
    if project.chapters:
        print("\n  章节列表:")
        for ch in sorted(project.chapters.values(), key=lambda c: c.sequence_number):
            status_icon = "✓" if ch.status.value == "completed" else "○"
            print(f"    {status_icon} 第{ch.sequence_number:>3}章 《{ch.title}》 [{ch.status.value}] {ch.word_count}字")


def cmd_character_add(args, pipeline: CreationPipeline, storage: JSONStorage):
    """添加人物"""
    project = _load_project(storage, args.project)
    role = CharacterRole(args.role) if args.role else CharacterRole.SUPPORTING

    kwargs = {}
    if args.personality:
        kwargs["personality"] = args.personality
    if args.motivation:
        kwargs["motivation"] = args.motivation
    if args.background:
        kwargs["background"] = args.background

    char = pipeline.add_character(project, name=args.name, role=role, **kwargs)
    print(f"人物已添加: {char.name} ({char.role.value}) ID={char.id}")


def cmd_world_set(args, pipeline: CreationPipeline, storage: JSONStorage):
    """设置世界观（从 JSON 文件）"""
    project = _load_project(storage, args.project)
    if not args.file:
        print("错误: 请使用 --file 指定世界观 JSON 文件")
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    world = WorldBuilding.from_dict(data)
    project.world = world
    project.updated_at = __import__("datetime").datetime.now().isoformat()
    storage.save(project)
    print(f"世界观已设置: {world.name}")


def cmd_outline_import(args, pipeline: CreationPipeline, storage: JSONStorage):
    """从 JSON 文件导入大纲"""
    project = _load_project(storage, args.project)
    if not args.file:
        print("错误: 请使用 --file 指定大纲 JSON 文件")
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)

    outline = OutlineNode.from_dict(data)
    pipeline.set_outline(project, outline)
    print(f"大纲已导入，共 {len(outline.flatten_chapters())} 章")


def cmd_generate_chapter(args, pipeline: CreationPipeline, storage: JSONStorage):
    """生成章节"""
    project = _load_project(storage, args.project)

    # 定位章节
    chapter = None
    if args.chapter:
        chapter = project.chapters.get(args.chapter)
    elif args.seq:
        for ch in project.chapters.values():
            if ch.sequence_number == args.seq:
                chapter = ch
                break

    if not chapter:
        print("错误: 找不到指定章节，请使用 --chapter <ID> 或 --seq <序号>")
        sys.exit(1)

    print(f"正在生成: 第{chapter.sequence_number}章 《{chapter.title}》...")
    print(f"  大纲: {chapter.outline_summary[:60]}...")

    if args.stream:
        def on_chunk(chunk: str):
            print(chunk, end="", flush=True)
        print("\n--- 生成内容 ---\n")
        pipeline.generate_chapter(
            project, chapter.id,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            stream_callback=on_chunk,
        )
        print("\n\n--- 生成结束 ---")
    else:
        chapter = pipeline.generate_chapter(
            project, chapter.id,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        print(f"生成完成: {chapter.word_count} 字")
        print(f"内容预览:\n{chapter.content[:300]}...")


def cmd_export(args, pipeline: CreationPipeline, storage: JSONStorage):
    """导出小说"""
    project = _load_project(storage, args.project)
    path = pipeline.export_project(project, format=args.format)
    print(f"已导出到: {path}")


def cmd_quickstart(args, pipeline: CreationPipeline, storage: JSONStorage):
    """快速启动：创建一个带示例数据的项目"""
    project = pipeline.initialize_project(
        title="示例小说：星际觉醒",
        author="XSAgent",
        description="一个用于演示的科幻小说项目",
    )

    # 添加世界观
    pipeline.add_world_setting(
        project,
        name="银河联邦纪元",
        genre="科幻",
        era="公元 3047 年",
        power_system="跃迁引擎技术、基因强化、神经接口。跃迁需要消耗反物质燃料，短距跃迁冷却 72 小时。",
        rules=[
            "跃迁不能在大质量天体引力井内进行",
            "基因强化有排异风险，非法改造者称为'蚀化者'",
            "神经接口直接连接会导致意识过载",
        ],
    )

    # 添加人物
    c1 = pipeline.add_character(
        project, name="林澈", role=CharacterRole.PROTAGONIST,
        personality="冷静、理性，内心有未愈合的创伤",
        motivation="寻找失踪的妹妹，揭开'蚀化者'背后的真相",
        arc="从孤独的走私者成长为联邦的关键变革者",
    )
    c2 = pipeline.add_character(
        project, name="艾薇", role=CharacterRole.DEUTERAGONIST,
        personality="活泼果敢，技术天才，嘴硬心软",
        motivation="证明自己比身为将军的父亲更优秀",
    )
    c3 = pipeline.add_character(
        project, name="零号", role=CharacterRole.ANTAGONIST,
        personality="神秘、优雅，对人类情感有扭曲的理解",
        motivation="认为人类必须通过'蚀化'才能进化",
    )

    # 设置关系
    c1.relationships[c2.name] = "搭档/逐渐信任"
    c1.relationships[c3.name] = "宿敌/本质相似"
    c2.relationships[c1.name] = "依赖的伙伴"

    # 创建大纲
    outline = OutlineNode(
        title="第一卷：暗流",
        level=1,
        summary="林澈在边缘星区偶然发现妹妹的线索，被迫卷入联邦与蚀化者的暗战。",
        children=[
            OutlineNode(
                title="第一章：走私者的日常",
                level=3,
                summary="林澈在废弃空间站交货，收到一条来自妹妹的加密求救信号。",
                plot_points=["展示林澈的日常生活与走私技能", "收到加密信号", "决定追查信号来源"],
                characters_involved=[c1.id],
                emotional_tone="紧张中带有些许孤独",
            ),
            OutlineNode(
                title="第二章：不速之客",
                level=3,
                summary="联邦特工艾薇找上门来，两人的初次交锋充满火药味。",
                plot_points=["艾薇追踪走私线索找到林澈", "双方短暂交手", "发现彼此目标一致，被迫合作"],
                characters_involved=[c1.id, c2.id],
                emotional_tone="冲突、试探、不信任",
            ),
        ]
    )
    pipeline.set_outline(project, outline)

    print(f"示例项目已创建!")
    print(f"  ID: {project.id}")
    print(f"  标题: {project.title}")
    print(f"\n接下来你可以:")
    print(f"  python main.py status --project {project.id}")
    print(f"  python main.py generate chapter --project {project.id} --seq 1")


def main():
    parser = argparse.ArgumentParser(
        prog="XSAgent",
        description="AI 辅助小说创作系统",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init
    p_init = subparsers.add_parser("init", help="初始化新项目")
    p_init.add_argument("--title", required=True, help="小说标题")
    p_init.add_argument("--author", default="", help="作者名")
    p_init.add_argument("--description", default="", help="简介")

    # list
    subparsers.add_parser("list", help="列出所有项目")

    # status
    p_status = subparsers.add_parser("status", help="查看项目状态")
    p_status.add_argument("--project", required=True, help="项目ID")

    # character add
    p_char = subparsers.add_parser("character", help="人物管理")
    char_sub = p_char.add_subparsers(dest="char_cmd")
    p_char_add = char_sub.add_parser("add", help="添加人物")
    p_char_add.add_argument("--project", required=True, help="项目ID")
    p_char_add.add_argument("--name", required=True, help="人物姓名")
    p_char_add.add_argument("--role", choices=[r.value for r in CharacterRole], default="supporting", help="角色定位")
    p_char_add.add_argument("--personality", default="", help="性格")
    p_char_add.add_argument("--motivation", default="", help="动机")
    p_char_add.add_argument("--background", default="", help="背景")

    # world set
    p_world = subparsers.add_parser("world", help="世界观管理")
    world_sub = p_world.add_subparsers(dest="world_cmd")
    p_world_set = world_sub.add_parser("set", help="从文件设置世界观")
    p_world_set.add_argument("--project", required=True, help="项目ID")
    p_world_set.add_argument("--file", required=True, help="JSON 文件路径")

    # outline import
    p_outline = subparsers.add_parser("outline", help="大纲管理")
    outline_sub = p_outline.add_subparsers(dest="outline_cmd")
    p_outline_import = outline_sub.add_parser("import", help="从文件导入大纲")
    p_outline_import.add_argument("--project", required=True, help="项目ID")
    p_outline_import.add_argument("--file", required=True, help="JSON 文件路径")

    # generate chapter
    p_gen = subparsers.add_parser("generate", help="生成内容")
    gen_sub = p_gen.add_subparsers(dest="gen_cmd")
    p_gen_ch = gen_sub.add_parser("chapter", help="生成章节")
    p_gen_ch.add_argument("--project", required=True, help="项目ID")
    p_gen_ch.add_argument("--chapter", default=None, help="章节ID")
    p_gen_ch.add_argument("--seq", type=int, default=None, help="章节序号")
    p_gen_ch.add_argument("--temperature", type=float, default=0.7, help="生成温度")
    p_gen_ch.add_argument("--max-tokens", type=int, default=4000, help="最大token数")
    p_gen_ch.add_argument("--stream", action="store_true", help="流式输出")

    # export
    p_export = subparsers.add_parser("export", help="导出小说")
    p_export.add_argument("--project", required=True, help="项目ID")
    p_export.add_argument("--format", choices=["txt", "md"], default="txt", help="导出格式")

    # quickstart
    subparsers.add_parser("quickstart", help="创建带示例数据的演示项目")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 加载配置
    config = load_config()
    model_cfg = config.get("model", {})
    storage_cfg = config.get("storage", {})
    skills_cfg = config.get("skills", {})

    # 初始化组件
    storage = JSONStorage(base_dir=storage_cfg.get("base_dir", "projects"))
    skill_registry = SkillRegistry()
    if skills_cfg.get("load_builtin", True):
        skill_registry.load_builtin_skills()
    for d in skills_cfg.get("custom_dirs", []):
        skill_registry.load_from_directory(d)

    # 初始化生成器（如有配置）
    generator = None
    backend = model_cfg.get("backend")
    if backend:
        try:
            generator = GeneratorFactory.create(backend, model_cfg)
            print(f"[系统] 已连接模型: {generator.get_name()}")
        except Exception as e:
            print(f"[警告] 模型初始化失败: {e}")
    else:
        print("[提示] 未配置 AI 模型，生成命令将不可用。请在 config.yaml 中设置 model.backend")

    pipeline = CreationPipeline(
        storage=storage,
        skill_registry=skill_registry,
        generator=generator,
    )

    # 路由命令
    if args.command == "init":
        cmd_init(args, pipeline, storage)
    elif args.command == "list":
        cmd_list(args, pipeline, storage)
    elif args.command == "status":
        cmd_status(args, pipeline, storage)
    elif args.command == "character" and args.char_cmd == "add":
        cmd_character_add(args, pipeline, storage)
    elif args.command == "world" and args.world_cmd == "set":
        cmd_world_set(args, pipeline, storage)
    elif args.command == "outline" and args.outline_cmd == "import":
        cmd_outline_import(args, pipeline, storage)
    elif args.command == "generate" and args.gen_cmd == "chapter":
        cmd_generate_chapter(args, pipeline, storage)
    elif args.command == "export":
        cmd_export(args, pipeline, storage)
    elif args.command == "quickstart":
        cmd_quickstart(args, pipeline, storage)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
