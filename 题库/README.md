# 深圳初中数学题库

将仓库下载到本机，用浏览器打开 [题库首页](index.html)。在「按试卷浏览」中可勾选学校和年级学期，如「七年级上学期」。在「按知识点与考点找题」中还可以勾选多个知识点或考点，每组都有「全选」和「取消全选」。同组勾选多项会显示命中其中任一项的结果，不同组的条件同时生效。浏览所需的脚本和数学排版资源随仓库提供。也可用静态文件服务器托管本目录。

## 首批资料

| 学校 | 学年／学期 | 原卷目录 | 大题 | 显式小问 |
| --- | --- | --- | ---: | ---: |
| 深圳实验学校初中部 | 2024–2025 学年七上期末 | [封面与题序](papers/SZ-SY-CZB-2024-25-G7-T1-FINAL.json) | 20 | 18 |
| 深圳市高级中学 | 2024–2025 学年七上期末 | [封面与题序](papers/SZ-GJ-2024-25-G7-T1-FINAL.json) | 20 | 19 |

两卷共有 27 道无小问的题目和 37 个显式小问，对应 64 个可检索的练习单元。整卷页面按照封面的 `question_ids` 展示 40 道原题。专项检索只返回命中的练习单元。示例考点 `E.S01.04.01`「用样本比例估计总体数量」对应实验第 16（4）问和高级第 17（4）问。

在「按知识点与考点找题」勾选该考点，再在「学校」中仅勾选「深圳实验学校初中部」，列表应仅剩第 16（4）问。打开后可查跳绳调查表、统计图和原卷第 4 页，展开解答可核对估计结果约 1700 人。在「学校」中点「全选」，即可看到高级第 17（4）问，估计结果约 2430 人。

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

## 新增一份试卷

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
