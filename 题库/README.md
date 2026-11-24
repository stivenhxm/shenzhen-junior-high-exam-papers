# 深圳初中数学题库

将仓库下载到本机，用浏览器打开 [题库首页](index.html)。在「按试卷浏览」中可勾选学校和年级学期，如「七年级上学期」。在「按知识点与考点找题」中还可以勾选多个知识点或考点，每组都有「全选」和「取消全选」。同组勾选多项会显示命中其中任一项的结果，不同组的条件同时生效。浏览所需的脚本和数学排版资源随仓库提供。也可用静态文件服务器托管本目录。

## 已入库的资料

七年级上学期原始目录中的 **260 个文件已全部登记**，包括 **117 份试卷、2,503 道大题、1,918 个显式小问**。可独立检索的 3,756 个练习单元由无小问的大题和有小问的各个小问组成。覆盖 2020–2021、2022–2023、2023–2024、2024–2025 四个学年。试卷数包含试题、选项或题序有实质差异的不同版本。

本轮在已有 32 份基础上增加 85 份，计 1,851 道大题。每个源文件都记录了仓内路径、SHA-256、用途和固定试卷编号。三组经比对确认的同卷异本附有比对说明。答题卡与打印版归到对应试卷。按文件核对或准备下一次增量入库时，使用[七上来源清单](batches/七年级上学期来源清单.json)。

可展开每道题的「答案与参考解答」对照原件。有些校方资料仅给答案，本轮据题补写了 65 道题的解法；成对解析中另有 1 道的原解栏为空，亦已补写。图表、手写评分稿和复杂排版可直接点图放大。知识点与考点沿用 v0.2，按小问保留完整匹配、部分匹配、仅知识点和判定依据。

[已解析试卷登记表](generated/已解析试卷.json)列出每份已入库的试卷 ID、学校、学期、考试类型、题量，以及原卷和配套解析的文件路径与指纹。登记表随索引一起生成，打开首页即可按学校检索。

2026 年 11 月 24 日新增 2024–2025 学年七上试卷 30 份，包括期末 3 份、期中 20 份、月考 7 份，共 612 道大题、539 个显式小问，可独立检索 972 个练习单元。与先前两份样卷合计 32 份、652 道大题。每题和小问保留资料答案、解法和出处。此批答案标为「据配套解析转录」，可展开原解析核对。[本批来源清单](batches/2026-11-24-g7-t1-01.json)

### 首批两份校勘样卷

| 学校 | 学年／学期 | 原卷目录 | 大题 | 显式小问 |
| --- | --- | --- | ---: | ---: |
| 深圳实验学校初中部 | 2024–2025 学年七上期末 | [封面与题序](papers/SZ-SY-CZB-2024-25-G7-T1-FINAL.json) | 20 | 18 |
| 深圳市高级中学 | 2024–2025 学年七上期末 | [封面与题序](papers/SZ-GJ-2024-25-G7-T1-FINAL.json) | 20 | 19 |

两卷共有 27 道无小问的题目和 37 个显式小问，对应 64 个可检索的练习单元。整卷页面按照封面的 `question_ids` 展示 40 道原题。专项检索只返回命中的练习单元。示例考点 `E.S01.04.01`「用样本比例估计总体数量」对应实验第 16（4）问和高级第 17（4）问。

在「按知识点与考点找题」勾选该考点，可找到深圳实验学校初中部期末第 16（4）问。打开后可查跳绳调查表、统计图和原卷第 4 页，展开解答可核对估计结果约 1700 人。深圳市高级中学期末第 17（4）问则使用另一份调查，估计结果约 2430 人。

## 文件与出处

| 路径 | 用途 |
| --- | --- |
| [../初中数学试卷/](../初中数学试卷/) | 原卷、配套解析和其他原始资料，封面通过仓库相对路径与 SHA-256 引用文件 |
| [papers/](papers/) | 一卷一份 JSON，包含学校、学年、年级、学期、考试类型、来源、打印版 PDF 和有序题目 ID |
| [questions/](questions/) | 一题一份 JSON，按试卷归档；题目、小问、校勘和材料在这里维护 |
| [assets/](assets/) | 原题图、解析图、原页裁图和 PDF。页码自 1 起，相对各自打印版计数 |
| [taxonomy/](taxonomy/) | 完整的 v0.2 知识点与考点目录，保存编号、名称和适用条件 |
| [schema/](schema/) | 试卷、题目 JSON 的字段格式 |
| [generated/](generated/) | 脚本生成的总目录、逐卷目录、反向索引、按 ID 读取的题面和答案分片 |

## 批量解析前查重

在本目录运行。查询单个源文件时，用实际原卷或解析版路径替换示例。

```shell
python scripts/registry.py "../初中数学试卷/…/原卷版.docx"
python scripts/registry.py --audit-g7
python scripts/batch_import.py plan batches/2026-11-24-g7-t1-01.json --output ../../outputs/next-batch/selection.json
```

`plan` 对照 `papers/` 中的已入库记录，同时去除同一待处理清单中的重复项。改过文件名的相同原卷以 SHA-256 识别，DOCX 被重新打包或仅修改编辑历史时，还会比对正文、嵌入公式和插图的内容指纹。同一路径换了原卷，或同一卷换了解析版，脚本会列出冲突供复核。可再次对上面的历史批次运行 `plan` 检查已登记数量。增删题目或重新排版的近似试卷需要再对照卷面。

新批次使用相同结构的清单。把新卷与解析版的仓内路径和 SHA-256、学校、学年、题名、考试类型、固定 ID 与答案段数填入清单。后续程序只使用 `plan --output` 生成的待处理清单。下例将中间文件集中在工作目录。

```shell
python scripts/batch_pages.py ../../outputs/next-batch/selection.json
python scripts/batch_content.py ../../outputs/next-batch/selection.json ../../outputs/next-batch/work/content
python scripts/batch_import.py apply ../../outputs/next-batch/selection.json --batch 新批次名
```

当前批处理支持带对应原卷与「【答案】」「【解析】」段落的 DOCX 资料。Word 排版打印需要 Windows、Microsoft Word、pywin32、PyMuPDF、numpy 与 Pillow。OOXML 和 MathType 抽取使用 lxml、Pillow 和固定版本的 [mtef-py 1.0.1](https://github.com/zhengdongjunjun/MTEF-py-FIX/tree/08818cf79ee10df67cc804d486c1fd9d772e189d)。每批在正式入库前校核小问、公式和图表，并根据真实题目补充 [v0.2 标签标注](scripts/batch_tag_reviews.json)。`apply` 核对来源、题号、页码、素材及标签，写入正式数据并重建索引与登记表。已登记的卷会跳过。

## 新增一份试卷

七上增加来源时，也请把新增文件的仓内路径、SHA-256、用途（原卷、解析或答案、答题卡等）及所关联的试卷 ID 加入来源清单。先登记新试卷封面与题目，再更新清单、重建索引并运行 `registry.py --audit-g7`。若新增的是已收录试卷的另一打印版，只需确认题意、选项和参考答案一致，再补登记该来源。

1. 将原卷和解析版放在仓库的 `初中数学试卷/` 中。两份来源各登记路径和 SHA-256；准备核对用的 PDF 与裁图，文件放在 `题库/assets/`。PDF 的页码对应当前登记的文件指纹。
2. 在 `papers/<paper_id>.json` 建封面。给这一卷分配唯一 ID；同校同学期的不同场次、A/B 卷须能区分。填写来源和 `question_ids`。按卷面顺序排列 ID，后续改题名、标签或目录顺序时沿用既有 ID。
3. 在 `questions/<paper_id>/<question_id>.json` 保存每道大题。可参考[有共享图表的统计题](questions/SZ-SY-CZB-2024-25-G7-T1-FINAL/SZ-SY-CZB-2024-25-G7-T1-FINAL-Q16.json)。`stem` 保存全题，`choices` 保存选项。行内公式用 LaTeX 的 `\(…\)`；`〔图1〕` 指向 `figures` 的第一项。表格的原文标记和行列数据一起保存。
4. 有小问时填写 `parts`。每个小问有永久 ID、原卷标签、可独立阅读的问法、所需 `material_ids`、前问依赖 `requires`、资料原答案 `given_answer`、复核答案 `answer` 和逐步解法 `solution_steps`。公共条件、统计图或原表放在本题 `materials`。作答前需要哪些材料，就引用哪些；需使用前问结论时指向该小问的 ID。作图题的完成图通过 `solution_figure_ids` 引用本题解析图。每问分别填写题面与解法页码，页内坐标以 PDF 左上角为原点，单位为点。
5. 从 v0.2 目录选各问实际考查的 `knowledge_ids` 和 `exam_ids`。覆盖情况记为「完整匹配」「部分匹配」或「仅知识点」；后两者写明 `tag_note`，仅知识点时考点列表留空。父题汇总其小问的标签。资料异文或算错时，保留 `given_answer`、`given_solution`，在复核答案与 `review_note` 中说明修正依据。未给的单题分值可填 `null`。
6. 在本目录用 Python 3.11 或更新版本运行以下命令，打开首页检查新卷题序、抽问材料和原卷页。提交主数据、资源及重建后的 `generated/`。仅改标签时，更新对应题和必要的父题汇总，然后执行同一组命令。

```shell
python scripts/build.py
python scripts/build.py check
```

`check` 会核对原资料与打印版的文件指纹、题目引用、标签、页码，以及已生成分片与当前数据是否一致。两份首发试卷的回归测试可用 `python -m unittest discover -s scripts/tests` 运行。

## 导出离线练习

在本目录运行。导出的 HTML 可作为单独一个文件带走。单卷导出可按原题序阅读；按考点导出只带命中的题目或小问，也可用固定 ID 明确挑题。

```shell
python scripts/build.py export --paper SZ-SY-CZB-2024-25-G7-T1-FINAL --output exports/shiyan-final.html
python scripts/build.py export --exam E.S01.04.01 --output exports/sample-estimation.html
python scripts/build.py export --items SZ-SY-CZB-2024-25-G7-T1-FINAL-Q16-P04 SZ-GJ-2024-25-G7-T1-FINAL-Q17-P04 --output exports/two-tasks.html
```
