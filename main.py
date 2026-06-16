from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

import jmcomic as _jmcomic
from jmcomic import download_album, Feature

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

        # 提取数字
        match = re.search(r"(\d+)", message_str)
        if not match:
            yield event.plain_result(f"请提供车牌号，例如：/jm 350234")
            return

        album_id = match.group(1)

        pdf_path = self.plugin_data_path / f"{album_id}.pdf"

        if pdf_path.exists():
            yield event.plain_result(f"本子 {album_id} 已存在，直接发送。")
        else:
            yield event.plain_result(f"开始获取: {album_id}")
            try:
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

                client = self.option.new_jm_client()
                if self.config.get("enable_cover_page"):
                    client.download_album_cover(
                        album_id, str(self.plugin_data_path / f"{album_id}_cover.png")
                    )
                    if self.config.get("enable_cover_page_blur"):
                        add_mosaic(
                            str(self.plugin_data_path / f"{album_id}_cover.png"),
                            str(self.plugin_data_path / f"{album_id}_cover_blur.png"),
                            self.config.get("blur_radius"),
                            0.4
                        )

                if self.config.get("enable_title") :
                    # 处理标题
                    album_detail = client.get_album_detail(album_id)
                    yield event.plain_result(
                        f"本子 {album_id} 标题: {album_detail.title}"
                    )
            except Exception as e:
                logger.error(f"下载本子 {album_id} 失败: {e}")
                yield event.plain_result(f"本子 {album_id} 下载失败: {e}")
                return

        if not pdf_path.exists():
            alt_path = Path(self.option.dir_rule.base_dir) / f"{album_id}.pdf"
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
                        name=f"{album_id}.pdf",
                    )
                except Exception as e:
                    logger.error(f"上传群文件失败: {e}")
                    chain.append(Comp.File(name=f"{album_id}.pdf", file=str(pdf_path)))
            else:
                chain.append(Comp.plain("无法上传群文件，直接发送 PDF 文件。"))
                chain.append(Comp.File(name=f"{album_id}.pdf", file=str(pdf_path)))
        else:
            chain = [
                Comp.Plain(
                    f"本子 {album_id} 下载完成！PDF密码: {self.config.get('PDF_secret')}，文件保存在：{pdf_path}"
                ),
            ]

        yield event.chain_result(chain)

    async def terminate(self):
        pass
