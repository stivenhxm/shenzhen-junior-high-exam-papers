"""Validate the canonical bank, build file://-compatible shards, or export offline practice."""
import argparse
import base64
import contextlib
import hashlib
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import registry


ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")
TOKEN = re.compile(r"\\\((?P<inline>[\s\S]*?)\\\)|\\\[(?P<display>[\s\S]*?)\\\]|〔图(?P<figure>\d+)〕")
COVER = {"完整匹配", "部分匹配", "仅知识点", "待标注"}
DIFFICULTY_KEYS = {"基础":"difficulty/basic", "进阶":"difficulty/intermediate", "挑战":"difficulty/challenge"}


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def js_literal(value):
    return compact(value).replace("<", r"\u003c").replace("\u2028", r"\u2028").replace("\u2029", r"\u2029")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_id(value):
    require(isinstance(value, str) and ID.fullmatch(value) and ".." not in value, f"无效 ID {value!r}")
    return value


def local(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative and not Path(relative).is_absolute()
            and not (":" in relative or ".." in Path(relative).parts), f"非仓内路径 {relative!r}")
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), f"找不到仓内文件 {relative}")
    return path


def file_hash(path):
    with path.open("rb") as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024), b""):
            hasher.update(chunk)
        return hasher.hexdigest()


def unique_map(records, context):
    items = {}
    for row in records:
        key = stable_id(row["id"])
        require(key not in items, f"{context} 重复 ID：{key}")
        items[key] = row
    return items


def uniq(values):
    return list(dict.fromkeys(values))


def text(value, context):
    require(isinstance(value, str) and value.strip(), f"{context} 为空")
    return value


def strings(values, context):
    require(isinstance(values, list) and values, f"{context} 须为非空列表")
    for value in values:
        text(value, context)
    return values


def tokens(value, figures):
    """Only escaped text, validated image paths and local KaTeX input enter the DOM."""
    result = []
    pos = 0
    for match in TOKEN.finditer(value):
        result.append(html.escape(value[pos:match.start()]))
        if match['figure'] is not None:
            n = int(match['figure'])
            require(1 <= n <= len(figures), f"无对应图：{match[0]}")
            result.append(f'<img class="figure" src="{html.escape(figures[n-1], quote=True)}" alt="原卷图 {n}">')
        else:
            display = match['display'] is not None
            tex = html.escape(match['display'] if display else match['inline'], quote=True)
            mode = ' data-display="block"' if display else ''
            result.append(f'<span class="bank-tex" data-tex="{tex}"{mode}>{html.escape(match[0])}</span>')
        pos = match.end()
    result.append(html.escape(value[pos:]))
    return "".join(result)


def paragraphs(value, q):
    for i, table in enumerate(q.get("tables", [])):
        value = value.replace(table["text"], f"〔原表{i}〕")
    out = []
    for line in value.splitlines():
        table = re.fullmatch(r"〔原表(\d+)〕", line.strip())
        if not table:
            if line.strip():
                out.append("<p>" + tokens(line, q["figures"]) + "</p>")
            continue
        rows = q["tables"][int(table[1])]["rows"]
        out.append('<div class="source-table"><table><tbody>')
        for row in rows:
            out.append("<tr>" + "".join("<td>"+"<br>".join(tokens(p, q["figures"]) for p in cell)+"</td>" for cell in row) + "</tr>")
        out.append("</tbody></table></div>")
    return "".join(out)


def prompt_html(q, task):
    if task["id"] == q["id"]:
        out = paragraphs(q["stem"], q)
        if q["choices"]:
            out += '<div class="choices">' + "".join(
                '<div class="choice"><b>'+html.escape(c["label"])+'.</b> <span>'+tokens(c["text"],q["figures"])+'</span></div>'
                for c in q["choices"]) + "</div>"
    else:
        materials = {m["id"]:m for m in q["materials"]}
        by_id = {p["id"]:p for p in q["parts"]}
        out = ""
        if task["material_ids"]:
            out += '<div class="shared-material"><h3>题目条件</h3>'
            for key in task["material_ids"]:
                out += paragraphs(materials[key]["text"], q)
            out += "</div>"
        if task["requires"]:
            out += '<div class="prerequisites"><h3>可用的前问结论</h3>'
            for key in task["requires"]:
                prior = by_id[key]
                out += "<p>" + tokens(prior["label"] + " " + prior["answer"], q["given_solution_figures"]) + "</p>"
            out += "</div>"
        out += '<div class="task-prompt"><h3>本小问</h3>'+paragraphs(task["prompt"], q)+'</div>'
    return '<div class="readable-stem">'+out+"</div>"


def source_for(q, task, role, paper):
    prefix = "question" if role == "paper" else "solution"
    pk, ik = prefix+"_pages", prefix+"_images"
    source = q["source"]
    pages = source[pk]
    images = source[ik]
    if role == "solution" and role not in paper["sources"]:
        require(q["solution_origin"] == "editorial_answer_and_solution" and not pages and not images
                and not task.get("source", {}).get(pk), f"{q['id']} 缺少解析来源或原解析定位有误")
        return {}
    limits = paper["sources"][role].get("print_page_count")
    require(pages and len(images)==len(pages) and len(set(pages))==len(pages)
            and all(isinstance(n,int) and n>0 and (not limits or n<=limits) for n in pages),
            f"{q['id']} {role} 页码与裁图不匹配")
    target = pages if task["id"] == q["id"] else task.get("source", {}).get(pk)
    require(target and set(target)<=set(pages), f"{task['id']} {role} 无法定位页码")
    return {pk:target,ik:[images[pages.index(n)] for n in target],role+"_pdf":paper["sources"][role]["rendered_pdf"]}


def curriculum_map(taxonomy, teaching):
    """Build one teaching hierarchy. Each exam point belongs to its primary knowledge point."""
    domains = unique_map(taxonomy["domains"], "领域")
    modules = unique_map(taxonomy["modules"], "模块")
    knowledge = unique_map(taxonomy["knowledge_points"], "知识点")
    exams = unique_map(taxonomy["exam_points"], "考点")
    knowledge_terms = teaching["knowledge"]
    exam_terms = teaching["exam_overrides"]
    require(knowledge_terms.keys()==knowledge.keys(), "教学学期表与知识点目录不一致")
    require(exam_terms.keys()<=exams.keys(), "教学学期表有未知考点")
    terms = teaching["terms"]
    term_set = set(strings(terms,"教学学期目录"))
    require(len(terms)==len(term_set), "教学学期重复")
    for code,row in (knowledge_terms | exam_terms).items():
        text(row["basis"],code+" 教学学期归属说明")
        refs = strings(row["source_refs"],code+" 册次来源")
        require(set(refs)<=teaching["sources"].keys(), f"{code} 的教学学期来源未登记")
        values = row["terms"]
        require(isinstance(values,list) and len(values)==len(set(values)) and set(values)<=term_set,
                f"{code} 教学学期无效：{values}")
    notes = teaching.get("term_notes", {})
    require(notes.keys()<=term_set, "学期说明引用了未知学期")

    domain_nodes = {d["name"]: {"id":d["id"], "name":d["name"], "modules":[]} for d in domains.values()}
    require(len(domains)==len(domain_nodes), "领域名称重复")
    module_nodes = {}
    for mod in modules.values():
        require(mod["domain"] in domain_nodes, f"模块 {mod['id']} 的领域无效")
        node = {"id":mod["id"], "name":mod["name"], "knowledge":[]}
        domain_nodes[mod["domain"]]["modules"].append(node)
        module_nodes[mod["id"]] = node
    placed = set()
    for kid,kp in knowledge.items():
        mid = kp["module_id"]
        require(mid in modules and kp["domain"]==modules[mid]["domain"], f"{kid} 的模块或领域无效")
        children = []
        for eid in kp["exam_point_ids"]:
            require(eid not in placed and eid in exams and exams[eid]["primary_knowledge_id"]==kid,
                    f"{kid} 的考点挂接无效：{eid}")
            placed.add(eid)
            assignment = exam_terms.get(eid, knowledge_terms[kid])
            children.append({"id":eid, "name":exams[eid]["name"], "terms":assignment["terms"]})
        module_nodes[mid]["knowledge"].append({"id":kid, "name":kp["name"], "terms":knowledge_terms[kid]["terms"], "exams":children})
    require(placed==exams.keys(),"教学图谱中有未挂接的考点")
    return {"terms":terms, "term_notes":{term:text(note,term+" 说明") for term,note in notes.items()},
            "domains":list(domain_nodes.values())}


def difficulty_indexes(shards, leaves, papers):
    paper_terms = {pid: p["grade"]+p["semester"] for pid,p in papers.items()}
    term_numbers = {term: i for i,term in enumerate(sorted(set(paper_terms.values())), 1)}
    groups = {level: {} for level in DIFFICULTY_KEYS}
    for row in leaves:
        if "difficulty" in row:
            term = paper_terms[row["paper_id"]]
            groups[row["difficulty"]].setdefault(term, []).append(row)
    catalog = []
    for level, by_term in groups.items():
        parts = []
        for term,rows in sorted(by_term.items()):
            key = f"{DIFFICULTY_KEYS[level]}-{term_numbers[term]}"
            shards[key] = {"level":level, "term":term, "results":rows}
            parts.append({"term":term, "count":len(rows), "key":key})
        if parts:
            catalog.append({"level":level, "count":sum(part["count"] for part in parts), "shards":parts})
    return catalog


def difficulty_counts(rows):
    counts = dict.fromkeys(DIFFICULTY_KEYS, 0)
    for row in rows:
        if "difficulty" in row:
            counts[row["difficulty"]] += 1
        else:
            for level, count in row.get("difficulty_counts", {}).items():
                counts[level] += count
    return {level:count for level,count in counts.items() if count}


class Bank:
    def __init__(self, root, *, unpublished=()):
        self.root = root
        self.shards = {}
        self.assets = set()
        self.papers = {}
        self.registered = []
        self.leaves = []
        self.rows = {}
        tax_files = sorted((root/"taxonomy").glob("taxonomy.v*.json"))
        require(tax_files, "缺少带版本的标签目录")
        teaching = read(root/"taxonomy"/"teaching-terms.v0.2.json")
        versions = {}
        for path in tax_files:
            tax = read(path)
            version = str(tax["metadata"]["version"])
            require(version not in versions, "重复标签目录版本 "+version)
            versions[version] = (unique_map(tax["knowledge_points"],path.name), unique_map(tax["exam_points"],path.name))
            if version == teaching["taxonomy_version"]:
                self.shards["curriculum"] = curriculum_map(tax, teaching)
        require("curriculum" in self.shards, "教学学期表引用了未知的标签目录版本")
        by_tag, tag_names, used = {}, {}, set()
        manifests = sorted((root/"papers").glob("*.json"))
        require(manifests, "缺少试卷目录")
        for path in manifests:
            p = read(path)
            pid = stable_id(p["id"])
            require(path.stem == pid and pid not in self.papers, f"试卷 ID 与文件名不符 {path.name}")
            require(str(p["schema_version"])=="1.0",f"{pid} 未支持的试卷数据版本")
            v = str(p["taxonomy_version"])
            require(v in versions, f"{pid} 未知目录版本 {v}")
            knowledge, exams = versions[v]
            for k,mapping in (("knowledge",knowledge),("exam",exams)):
                for code,row in mapping.items():
                    val = (k,row["name"])
                    require(code not in tag_names or tag_names[code]==val, f"跨版本标签语义冲突 {code}")
                    tag_names[code] = val
            require("paper" in p["sources"],pid+" 缺少原卷")
            for role in p["sources"]:
                src = p["sources"][role]
                relative = src.get("git_path") or src["repo_path"]
                original = local(root.parent,relative)
                require(file_hash(original)==src["sha256"], f"{pid} {role} 原文件指纹不符")
                pdf = self.asset(src["rendered_pdf"])
                if src.get("rendered_sha256"):
                    require(file_hash(pdf)==src["rendered_sha256"],f"{pid} {role} 打印版指纹不符")
            ids = p["question_ids"]
            require(len(ids)==len(set(ids)) and ids, f"{pid} 目录题号重复或为空")
            cover = {k:p[k] for k in ("id","school","title","academic_year","grade","semester","exam_type")}
            cover.update(count=len(ids),short_name=p.get("short_name",p["school"]))
            self.papers[pid] = cover
            results = []
            numbers = set()
            total_parts = 0
            for qid in ids:
                qpath = root/"questions"/pid/(stable_id(qid)+".json")
                q = read(qpath)
                used.add(qpath)
                require(q["id"]==qid and q["paper_id"]==pid and str(q["taxonomy_version"])==v, f"{qid} 归卷或版本错误")
                require(str(q["schema_version"])=="1.0",f"{qid} 未支持的题目数据版本")
                require(q["number"] not in numbers, f"{pid} 卷内题号重复 {q['number']}")
                numbers.add(q["number"])
                self.add_question(p,q,knowledge,exams,by_tag)
                total_parts += len(q['parts'])
                results.append(self.rows[qid])
            counts = difficulty_counts(results)
            if counts:
                cover["difficulty_counts"] = counts
            self.shards["papers/"+pid] = dict(cover,results=results)
            for field in ("metadata_note","edition_note"):
                if p.get(field):
                    self.shards["papers/"+pid][field]=p[field]
            self.registered.append(registry.make_entry(root.parent, p, total_parts))
        actual = {path for path in (root/"questions").glob("*/*.json") if path.parent.name not in unpublished}
        require(actual==used,"有题目未被试卷目录引用："+", ".join(str(p) for p in actual-used))
        tags = []
        for code,rows in sorted(by_tag.items()):
            k,title=tag_names[code]
            self.shards["tags/"+code] = {"id":code,"results":rows}
            tags.append({"id":code,"name":title,"kind":k,"count":len(rows)})
        self.shards["catalog"] = {"papers":list(self.papers.values()),"tags":tags,
                                  "difficulties":difficulty_indexes(self.shards,self.leaves,self.papers)}
        registry.attach_inventory(root,self.registered)
        self.registry_json = registry.as_json(self.registered)

    def asset(self, rel):
        require(rel.startswith("assets/"),f"题库资源应位于 assets/：{rel}")
        if rel not in self.assets:
            file = local(self.root,rel)
            self.assets.add(rel)
            return file
        return self.root/rel

    def add_question(self, paper, q, knowledge, exams, by_tag):
        qid = q["id"]
        origin = q["solution_origin"]
        text(q["stem"],qid+" stem")
        if origin not in {"source_solution_summary","source_checked_with_correction","source_facsimile","editorial_answer_and_solution"}:
            text(q["given_answer"],qid+" given_answer")
        if origin not in {"editorial_solution","source_answer_only","source_facsimile","editorial_answer_and_solution"}:
            text(q["given_solution"],qid+" given_solution")
        if origin in {"source_checked_with_correction","editorial_solution","editorial_answer_and_solution"}:
            text(q.get("review_note"),qid+" 校勘说明")
        for ref in q["figures"]+q["given_solution_figures"]+q["source"]["question_images"]+q["source"]["solution_images"]:
            self.asset(ref)
        for content,figures in [(q["stem"],q["figures"]), (q["given_answer"]+"\n"+q["given_solution"],q["given_solution_figures"])]:
            require(content.count(r"\(")==content.count(r"\)"),f"{qid} 有未闭合的行内公式")
            require(all(1<=int(n)<=len(figures) for n in re.findall(r"〔图(\d+)〕",content)),f"{qid} 原始图引用不存在")
        if q["type"] == "选择题" and len(q["choices"]) < 2:
            require(q.get("choices_in_facsimile") is True and q["figures"] and
                    re.search(r"〔图\d+〕",q["stem"]) and q["source"]["question_images"],f"{qid} 缺选项或选项影像")
        materials = unique_map(q["materials"],qid+" 材料")
        for mat in materials.values():text(mat["text"],qid+" 材料内容")
        for task in [q]+q["parts"]:
            key=stable_id(task["id"])
            require(key not in self.rows,f"题或小问 ID 重复 {key}")
            title = text(task.get("title", q["title"]), key+" 题名")
            text(task["answer"],key+" 答案")
            task_origin = task.get("solution_origin",origin)
            if task_origin in {"source_answer_only","source_facsimile"} and not task["solution_steps"]:
                require(bool(q["source"]["solution_images"]),key+" 缺原答案页影像")
            else:
                strings(task["solution_steps"],key+" 解法")
            require(task["coverage"] in COVER and (task["coverage"]=="完整匹配" or task.get("tag_note")),f"{key} 缺标签范围说明")
            pending = task["coverage"] == "待标注"
            require(bool(task["knowledge_ids"]) != pending and set(task["knowledge_ids"])<=knowledge.keys() and set(task["exam_ids"])<=exams.keys(),
                    f"{key} 缺知识点或包含未知标签")
            require(bool(task["exam_ids"]) == (task["coverage"] in {"完整匹配","部分匹配"}),f"{key} 考点与覆盖情况矛盾")
            require(all(exams[e]["primary_knowledge_id"] in task["knowledge_ids"] for e in task["exam_ids"]),f"{key} 主知识点不符")
            if key != qid:
                text(task["prompt"],key+" 独立问法")
                require(set(task["material_ids"])<=materials.keys(),f"{key} 缺少引用材料")
                require(all(pid in self.rows and self.rows[pid]["question_id"]==qid and pid!=qid for pid in task["requires"]), f"{key} 前问依赖越界或循环")
            for field in ("knowledge_ids","exam_ids"):
                require(len(set(task[field]))==len(task[field]),f"{key} 有重复的 {field}")
            self.rows[key] = {"id":key,"question_id":qid,"paper_id":q["paper_id"],"number":q["number"],"label":task.get("label",""),
                              "type":q["type"],"title":title,"preview":str(task.get("stem_text") or task.get("prompt") or q["stem"])[:180],
                              "knowledge_ids":task["knowledge_ids"],"exam_ids":task["exam_ids"],"coverage":task["coverage"],
                              "has_review_note":bool(task.get("review_note"))}
            if "difficulty" in task:
                rating = task["difficulty"]
                require(key != qid or not q["parts"], key+" 多小问题须逐问标难度")
                require(isinstance(rating,dict) and isinstance(rating.get("level"),str)
                        and rating["level"] in DIFFICULTY_KEYS, key+" 难度档位无效")
                text(rating.get("reason"),key+" 难度理由")
                self.rows[key]["difficulty"] = rating["level"]
        if q["parts"]:
            counts = difficulty_counts(self.rows[part["id"]] for part in q["parts"])
            if counts:
                self.rows[qid]["difficulty_counts"] = counts
        for task in [q]+q["parts"]:
            key = task["id"]
            row = self.rows[key]
            is_whole = key==qid
            if not is_whole or not q["parts"]:
                self.leaves.append(row)
                for code in uniq(task["knowledge_ids"]+task["exam_ids"]):
                    by_tag.setdefault(code,[]).append(row)
            else:
                for field in ["knowledge_ids","exam_ids"]:
                    require(all(set(p[field])<=set(task[field]) for p in q["parts"]),f"{qid} 缺子问汇总标签")
            body = prompt_html(q,task)
            figures = [html.unescape(path) for path in re.findall(r'<img class="figure" src="([^"]+)"', body)]
            self.shards["items/"+key] = dict(row, html=body, figures=uniq(figures),
                parts=[self.rows[p["id"]] for p in q["parts"]] if is_whole else [],source=source_for(q,task,"paper",paper),
                tag_reason=task.get("tag_reason",q["tag_reason"] if is_whole else ""),tag_note=task.get("tag_note",""),
                points=(q.get("points") if is_whole else task.get("points")))
            if "difficulty" in task:
                self.shards["items/"+key]["difficulty_reason"] = task["difficulty"]["reason"]
            solution_figure_ids = task.get("solution_figure_ids", [])
            if is_whole:
                # Readers opening a complete question also need each worked subquestion's diagram.
                solution_figure_ids = uniq([*solution_figure_ids, *(n for part in q["parts"] for n in part.get("solution_figure_ids", []))])
            require(all(type(i) is int and 1<=i<=len(q["given_solution_figures"]) for i in solution_figure_ids),f"{key} 解答所需图号越界")
            self.shards["answers/"+key] = {
                "answer":task["answer"],"solution_steps":task["solution_steps"],"given_answer":task.get("given_answer",""),
                "given_solution":task.get("given_solution",""),"solution_origin":task.get("solution_origin",q["solution_origin"]),
                "review_note":task.get("review_note",""),"source":source_for(q,task,"solution",paper),
                "solution_figures":[q["given_solution_figures"][n-1] for n in solution_figure_ids]
            }
            for field,group in (("supplemental_papers","items"),("supplemental_solutions","answers")):
                more = task.get("source",{}).get(field,[])
                if not more:
                    continue
                for ref in more:
                    target = self.asset(ref["pdf"])
                    require(file_hash(target)==ref.get("rendered_sha256",ref["sha256"]) and
                            file_hash(local(self.root.parent,ref["git_path"]))==ref["sha256"],
                            f"{key} 补充来源指纹不符")
                    require(ref["pages"] and all(type(n) is int and 1 <= n <= ref["print_page_count"] for n in ref["pages"]),
                            f"{key} 补充来源页码越界")
                self.shards[group+"/"+key][field]=more
            displayed = [task["answer"], *task["solution_steps"], task.get("given_answer", "")]
            cited = sorted({int(n) for line in displayed for n in re.findall(r"〔图(\d+)〕", line)})
            if cited:
                require(all(1 <= n <= len(q["given_solution_figures"]) for n in cited), f"{key} 答案中有未定位的图")
                self.shards["answers/"+key]["figure_refs"] = {str(n):q["given_solution_figures"][n-1] for n in cited}


@contextlib.contextmanager
def publish_lock(root):
    # OS locks are released when a build is interrupted. The lockfile lives outside the repo.
    name = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:20]
    with (Path(tempfile.gettempdir())/("exam-bank-"+name+".lock")).open("a+b") as lock:
        if os.name=="nt":
            import msvcrt
            lock.seek(0,os.SEEK_END)
            if not lock.tell():
                lock.write(b"1")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock,fcntl.LOCK_UN)


def expression(key,value):
    return "globalThis.BankData.put("+js_literal(key)+","+js_literal(value)+");\n"


def check_generated(bank):
    directory=bank.root/"generated"
    require((directory/registry.NAME).read_text(encoding='utf8') == bank.registry_json, '已解析试卷登记表需要重建')
    expected={key+".js" for key in bank.shards}
    found={p.relative_to(directory).as_posix() for p in directory.rglob("*.js")}
    require(expected==found, "生成分片缺失或多余，请重建：" + ", ".join(sorted(expected^found)[:4]))
    for key,value in bank.shards.items():
        path=directory/(key+".js")
        require(path.read_text(encoding="utf8")==expression(key,value),f"分片与当前数据不一致：{key}，请重建")


def publish(root):
    target = root/"generated"
    backup = root/".generated-previous"
    with publish_lock(root):
        # Restore the previous complete build if the last process died between the two renames.
        if backup.is_dir():
            require(backup.resolve().parent==root and not backup.is_symlink() and (backup/"catalog.js").is_file(),
                    f"发现不属于本构建器的备份目录：{backup}")
            if target.is_dir():
                shutil.rmtree(backup)
            else:
                backup.rename(target)
        bank=Bank(root)
        stage=Path(tempfile.mkdtemp(prefix=".generated-stage-",dir=root))
        try:
            (stage/registry.NAME).write_text(bank.registry_json, encoding='utf8', newline='\n')
            for key,val in bank.shards.items():
                dest=stage/(key+".js")
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(expression(key,val),encoding="utf-8",newline="\n")
            if target.exists():
                require(target.is_dir() and not target.is_symlink() and (target/"catalog.js").is_file(),
                        "generated/ 已存在但不是已构建的目录")
                target.rename(backup)
            try:
                stage.rename(target)
            except BaseException:
                if backup.exists():
                    backup.rename(target)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return bank


def curriculum_subset(curriculum, tag_ids):
    """Keep exported tags and their ancestors, in the same order as the full map."""
    def branches(nodes, child_fields):
        selected = []
        for node in nodes:
            if child_fields:
                first, *rest = child_fields
                children = branches(node[first], rest)
                if children or node["id"] in tag_ids:
                    selected.append({**node, first:children})
            elif node["id"] in tag_ids:
                selected.append(node)
        return selected

    return {**curriculum, "domains":branches(curriculum["domains"], ["modules","knowledge","exams"])}


def subset(bank,args):
    if args.paper:
        require(args.paper in bank.papers,f"找不到试卷 {args.paper}")
        selection = [r["id"] for r in bank.shards["papers/"+args.paper]["results"]]
    elif args.exam or args.knowledge:
        tag = args.exam or args.knowledge
        kind="exam" if args.exam else "knowledge"
        require(any(t["id"]==tag and t["kind"]==kind for t in bank.shards["catalog"]["tags"]),f"没有已标注的标签 {tag}")
        selection=[r["id"] for r in bank.shards["tags/"+tag]["results"]]
    else:
        selection=uniq(args.items)
    require(all(k in bank.rows for k in selection),"不认识的题目或小问 ID："+", ".join(k for k in selection if k not in bank.rows))
    if args.school:
        selection=[k for k in selection if bank.papers[bank.rows[k]["paper_id"]]["school"]==args.school]
    require(selection,"没有符合条件的题目")
    # Deliberately include only the selected tasks in a practice file. A selected whole question
    # carries its own subquestions; selecting a single part never imports unrelated siblings.
    available=set(selection)
    for key in selection:
        available.update(s["id"] for s in bank.shards["items/"+key]["parts"])
    pids=uniq(bank.rows[k]["paper_id"] for k in selection)
    data={}
    rows=bank.rows
    covers=[]
    for pid in pids:
        cover=bank.papers[pid]
        picked=[r for r in bank.shards["papers/"+pid]["results"] if r["id"] in available]
        if args.paper:
            data["papers/"+pid]=dict(cover,results=picked)
        covers.append(cover)
    tags=[]
    for t in bank.shards["catalog"]["tags"]:
        source=bank.shards["tags/"+t["id"]]
        filtered=[r for r in source["results"] if r["id"] in available]
        if filtered:
            tags.append(dict(t,count=len(filtered)))
            data["tags/"+t["id"]]={"id":t["id"],"results":filtered}
    data["catalog"]={"tags":tags,"papers":covers,
                     "difficulties":difficulty_indexes(data,(r for r in bank.leaves if r["id"] in available),bank.papers)}
    data["curriculum"]=curriculum_subset(bank.shards["curriculum"],{t["id"] for t in tags})
    paths=set()
    for key in sorted(available):
        for group in ("items","answers"):
            shard = bank.shards[group+"/"+key]
            data[group+"/"+key]=shard
            for field in ("question_images","solution_images"):
                paths.update(shard["source"].get(field,[]))
            for field in ("paper_pdf","solution_pdf"):
                if field in shard["source"]:
                    paths.add(shard["source"][field])
            paths.update(shard.get("figures",[]))
            paths.update(shard.get("solution_figures",[]))
            paths.update(ref["pdf"] for ref in shard.get("supplemental_solutions",[]))
            paths.update(ref["pdf"] for ref in shard.get("supplemental_papers",[]))
            paths.update(shard.get("figure_refs",{}).values())
    assets={}
    for rel in sorted(paths):
        content=local(bank.root,rel).read_bytes()
        mime=mimetypes.guess_type(rel)[0] or "application/octet-stream"
        assets[rel]="data:"+mime+";base64,"+base64.b64encode(content).decode("ascii")
    return {"data":data,"assets":assets,"results":[rows[k] for k in selection],
            "start":{"mode":"paper" if args.paper else "practice","ids":selection,"key":args.paper or args.exam or args.knowledge or ""}}


def embedded_script(code):
    return "<script>"+re.sub(r"</script",lambda _:r"<\/script",code,flags=re.I)+"</script>"


def export(bank,args):
    payload=subset(bank,args)
    root=bank.root
    template=(root/"index.html").read_text(encoding="utf-8-sig")
    placeholder='<script id="bank-offline"></script>'
    require(placeholder in template,"浏览入口缺少 bank-offline 注入点")
    template=template.replace(placeholder,embedded_script("window.BANK_OFFLINE="+js_literal(payload)+";"))
    math='<script id="bank-math-offline"></script>'
    if math in template:
        template=template.replace(math,embedded_script(local(root,"web/vendor/katex.min.js").read_text(encoding="utf8")))
    def script(match):
        return embedded_script(local(root,match[1]).read_text(encoding="utf-8-sig"))
    def style(match):
        return "<style>"+local(root,match[1]).read_text(encoding="utf-8-sig")+"</style>"
    template=re.sub(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</script>',script,template,flags=re.I)
    template=re.sub(r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])[^>]*\bhref=["\']([^"\']+)["\'][^>]*>',style,template,flags=re.I)
    dest=args.output.resolve()
    require(dest.suffix.lower()==".html" and dest!=root/"index.html","导出目标须为独立的 .html 文件")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf8",newline="\n",suffix=".tmp",delete=False,dir=dest.parent) as stream:
        tmp=Path(stream.name)
        try:
            stream.write(template)
        except BaseException:
            stream.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp,dest)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"{dest}（{len(payload['results'])} 个选中条目）")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT,help="题库根目录")
    cmds=parser.add_subparsers(dest="cmd")
    cmds.add_parser("build",help="重建全部静态分片（默认）")
    cmds.add_parser("validate",help="校验档案、题目、来源文件、标签及依赖，不写入文件")
    cmds.add_parser("check",help="校验源数据并逐一检查所有已生成的分片是否同步")
    ex=cmds.add_parser("export",help="以同一浏览界面导出单文件 HTML")
    selection=ex.add_mutually_exclusive_group(required=True)
    selection.add_argument("--paper",metavar="PAPER_ID")
    selection.add_argument("--exam",metavar="EXAM_ID")
    selection.add_argument("--knowledge",metavar="KNOWLEDGE_ID")
    selection.add_argument("--items",metavar="TASK_ID",nargs="+")
    ex.add_argument("--school",help="完整学校名称，可进一步缩小范围")
    ex.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve()
    bank=publish(root) if args.cmd in (None,"build") else Bank(root)
    if args.cmd=="check":
        check_generated(bank)
    if args.cmd=="export":
        export(bank,args)
    else:
        count=sum(x["count"] for x in bank.papers.values())
        print(f"{len(bank.papers)} 份试卷，{count} 道大题，{len(bank.leaves)} 个检索单元，{len(bank.shards['catalog']['tags'])} 个已用标签")


if __name__=="__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError) as error:
        print("题库构建失败："+str(error),file=sys.stderr)
        sys.exit(1)
