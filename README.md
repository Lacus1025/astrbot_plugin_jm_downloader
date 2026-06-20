# astrbot_plugin_jm_downloader

JMComic 本子下载插件 for AstrBot，支持下载为加密 PDF 并上传至群文件。

## 命令

- `/jm <车号>` — 下载指定本子，合并为加密 PDF，上传到群文件或返回文件路径
- `/jm <车号> <章节>` — 下载指定本子的特定章节，保存为 `{车号}_{章节}.pdf`
- `/jmclean` — 清理所有已下载的 PDF、封面图及临时目录

## 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `PDF_secret` | string | `jmcomic` | PDF 查看密码 |
| `enable_title` | bool | — | 是否启用标题显示 |
| `enable_cover_page` | bool | — | 是否启用封面显示 |
| `enable_cover_page_blur` | bool | — | 是否启用封面模糊（马赛克）处理 |
| `blur_radius` | int | `10` | 封面模糊处理的模糊半径 |

## 依赖

- `jmcomic`
- `Pillow`
- `img2pdf`

已包含于 `requirements.txt`。
