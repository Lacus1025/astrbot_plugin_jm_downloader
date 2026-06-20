from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

import jmcomic as _jmcomic
from jmcomic import download_album, download_photo, Feature

import base64
import os
from pathlib import Path
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
import re

from PIL import Image


def add_mosaic(image_path, output_path, block_size=20, area_ratio=0.4):
    # 打开图片
    img = Image.open(image_path)
    w, h = img.size

    # 计算中间区域
    mh = int(h * area_ratio)
    top = (h - mh) // 2

    # 裁剪中间区域
    region = img.crop((0, top, w, top + mh))
    small = region.resize((w // block_size, mh // block_size), Image.NEAREST)
    mosaic = small.resize((w, mh), Image.NEAREST)

    # 贴回原图
    img.paste(mosaic, (0, top))
    img.save(output_path)


@register(
    "astrbot_plugin_jm_downloader", "Lacus1025", "JM Downloader for AstrBot", "1.0.0"
)
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_data_path = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_jm_downloader"
        )
        self.plugin_data_path.mkdir(parents=True, exist_ok=True)
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.option = _jmcomic.create_option_by_file(f"{plugin_dir}/option.yml")
        self.option.dir_rule.base_dir = str(self.plugin_data_path)

    async def initialize(self):
        pass

    @filter.command("jm")
    async def jm(self, event: AstrMessageEvent):
        message_str = event.message_str.strip()

        match = re.search(r"(\d+)\s*(\d*)", message_str)
        if not match or not match.group(1):
            yield event.plain_result(f"请提供车牌号，例如：/jm 350234")
            return

        album_id = match.group(1)
        chapter = int(match.group(2)) if match.group(2) else None

        pdf_name = f"{album_id}_{chapter}.pdf" if chapter else f"{album_id}.pdf"
        pdf_path = self.plugin_data_path / pdf_name

        if pdf_path.exists():
            yield event.plain_result(f"本子 {album_id} 已存在，直接发送。")
        else:
            yield event.plain_result(f"开始获取: {album_id}")
            try:
                client = self.option.new_jm_client()
                album_detail = None

                if chapter:
                    album_detail = client.get_album_detail(album_id)
                    if chapter < 1 or chapter > len(album_detail):
                        yield event.plain_result(
                            f"章节号超出范围，本子共 {len(album_detail)} 章"
                        )
                        return
                    photo_id = album_detail.episode_list[chapter - 1][0]
                    download_photo(
                        photo_id,
                        self.option,
                        extra=Feature.export_pdf(
                            pdf_dir=str(self.plugin_data_path),
                            filename_rule="{Aid}_{Pindex}",
                            delete_original_file=True,
                            encrypt={"password": self.config.get("PDF_secret")},
                        ),
                    )
                else:
                    download_album(
                        album_id,
                        self.option,
                        extra=Feature.export_pdf(
                            pdf_dir=str(self.plugin_data_path),
                            filename_rule="Aid",
                            delete_original_file=True,
                            encrypt={"password": self.config.get("PDF_secret")},
                        ),
                    )

                if self.config.get("enable_cover_page"):
                    client.download_album_cover(
                        album_id, str(self.plugin_data_path / f"{album_id}_cover.png")
                    )
                    if self.config.get("enable_cover_page_blur"):
                        add_mosaic(
                            str(self.plugin_data_path / f"{album_id}_cover.png"),
                            str(self.plugin_data_path / f"{album_id}_cover_blur.png"),
                            self.config.get("blur_radius"),
                            self.config.get("blur_area_ratio"),
                        )

                if self.config.get("enable_title"):
                    if not chapter:
                        album_detail = client.get_album_detail(album_id)
                    yield event.plain_result(
                        f"本子 {album_id} 标题: {album_detail.title}"  # type: ignore[union-attr]
                    )

            except Exception as e:
                logger.error(f"下载本子 {album_id} 失败: {e}")
                yield event.plain_result(f"本子 {album_id} 下载失败: {e}")
                return

        if not pdf_path.exists():
            alt_path = Path(self.option.dir_rule.base_dir) / pdf_name
            if alt_path.exists():
                pdf_path = alt_path
            else:
                yield event.plain_result(
                    f"本子 {album_id} 下载完成，但未找到 PDF 文件。"
                )
                return

        if event.get_group_id():
            chain = []

            if self.config.get("enable_cover_page"):
                if self.config.get("enable_cover_page_blur"):
                    chain.append(
                        Comp.Image.fromFileSystem(
                            str(self.plugin_data_path / f"{album_id}_cover_blur.png")
                        )
                    )
                else:
                    chain.append(
                        Comp.Image.fromFileSystem(
                            str(self.plugin_data_path / f"{album_id}_cover.png")
                        )
                    )

            chain.append(
                Comp.Plain(
                    f"本子 {album_id} 下载完成！PDF密码: {self.config.get('PDF_secret')}，已上传至群文件。"
                )
            )
            if hasattr(event, "bot"):
                try:
                    with open(str(pdf_path), "rb") as f:
                        data = base64.b64encode(f.read()).decode()
                    await event.bot.call_action(
                        "upload_group_file",
                        group_id=int(event.get_group_id()),
                        file=f"base64://{data}",
                        name=pdf_name,
                    )
                except Exception as e:
                    logger.error(f"上传群文件失败: {e}")
                    chain.append(Comp.File(name=pdf_name, file=str(pdf_path)))
            else:
                chain.append(Comp.plain("无法上传群文件，直接发送 PDF 文件。"))
                chain.append(Comp.File(name=pdf_name, file=str(pdf_path)))
        else:
            chain = [
                Comp.Plain(
                    f"本子 {album_id} 下载完成！PDF密码: {self.config.get('PDF_secret')}，文件保存在：{pdf_path}"
                ),
            ]

        yield event.chain_result(chain)

    @filter.command("jmclean")
    async def jmclean(self, event: AstrMessageEvent):
        import shutil

        deleted = []
        for f in self.plugin_data_path.iterdir():
            if f.suffix in (".pdf", ".png"):
                f.unlink()
                deleted.append(f.name)
            elif f.is_dir():
                shutil.rmtree(f)
                deleted.append(f.name)

        if not deleted:
            yield event.plain_result("没有找到要删除的文件。")
        else:
            yield event.plain_result(
                "已删除以下文件/目录:\n" + "\n".join(f"  {d}" for d in deleted)
            )

    async def terminate(self):
        pass
