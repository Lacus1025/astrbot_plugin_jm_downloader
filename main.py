from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
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


@register(
    "astrbot_plugin_jm_downloader", "Lacus1025", "JM Downloader for AstrBot", "1.0.0"
)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
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

        yield event.plain_result(f"开始获取车牌: {album_id}")

        pdf_path = self.plugin_data_path / f"{album_id}.pdf"

        if pdf_path.exists():
            yield event.plain_result(f"本子 {album_id} 已存在，直接发送。")
        else:
            try:
                download_album(
                    album_id,
                    self.option,
                    extra=Feature.export_pdf(
                        pdf_dir=str(self.plugin_data_path),
                        filename_rule="Aid",
                        delete_original_file=True,
                        encrypt={"password": "saki"},
                    ),
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
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(f"本子 {album_id} 下载完成！密码: saki，已上传至群文件。"),
            ]
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
                chain.append(Comp.File(name=f"{album_id}.pdf", file=str(pdf_path)))
        else:
            chain = [
                Comp.At(qq=event.get_sender_id()),
                Comp.Plain(
                    f"本子 {album_id} 下载完成！密码: saki，文件保存在：{pdf_path}"
                ),
            ]

        yield event.chain_result(chain)

    async def terminate(self):
        pass
