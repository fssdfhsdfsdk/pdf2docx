import sys

import fitz
from pprint import pprint
import math
import re
import pyperclip

test_demo_path = r"D:\pdf2docx\test\samples\demo-section.pdf"
book1 = r"H:\pdf\CS计算机\网络\TCPIP Illustrated, Volume 1 The Protocols by Kevin R. Fall, W. Richard Stevens (z-lib.org).pdf"

doc = fitz.open(book1)  # open a document
out = open("output.txt", "wb")  # create a text output
out_html = open("output.html", "w+")  # create a text output
out_book1 = open("output_book1.txt", "w")  # create a text output


def get_pages_text(index_s, count=1):
    for idx in range(index_s, index_s + count):
        page = doc[idx]
        text = page.get_text().encode("utf8")  # get plain text (is in UTF-8)
        # out.write(text)  # write text of page
        # out.write(bytes((12,)))  # write page delimiter (form feed 0x0C)

        tx_p = page.get_textpage()
        blocks = tx_p.extractBLOCKS()
        for block in blocks:
            print(block)

        dict4 = tx_p.extractDICT()

        wrods = tx_p.extractWORDS()
        htmls = tx_p.extractHTML()
        out_html.write(htmls)

        tabs = page.find_tables()  # locate and extract any tables on page
        print(f"{len(tabs.tables)} found on {page}")  # display number of found tables
        if tabs.tables:  # at least one table found?
            pprint(tabs[0].extract())  # print content of first table


def get_line_texts(line):
    outs = []
    for span in line['spans']:
        outs.append(span['text'])
    return " ".join(outs)


def get_lines_texts(lines, spl: str = " "):
    outs = []
    for line in lines:
        for span in line['spans']:
            outs.append(span['text'])
    return spl.join(outs)


def get_block_texts(block, spl: str, start_line=None, line_limit=None):
    """
    start_line: 初始行号
    line_limit： 总数量
    """
    outs = []
    if start_line is None:
        start_line = 0
    lines = block['lines']
    cnt = len(lines)

    num = 0
    while start_line < cnt:
        num += 1
        if line_limit is not None:
            if num > line_limit:
                break
        line = lines[start_line]
        for span in line['spans']:
            outs.append(span['text'])
        start_line += 1
    return spl.join(outs)


def check_is_code_blocks(block):
    flag = False
    code_line = 0
    for line in block['lines']:
        spans = line['spans']
        if len(spans) == 1 and spans[0]['font'] == "TheSansMonoCondensed-Sem":
            flag = True
            code_line += 1
    return flag, code_line


def check_title_blocks(block):
    lines = block['lines']
    if len(lines) == 1:
        s1 = lines[0]['spans'][0]
        if s1['font'] == "Myriad-CnSemibold":
            size = s1['size']
            if math.floor(size) == 11:
                return "##### " + s1['text']
            elif math.floor(size) == 15:
                return "#### " + s1['text']
            elif math.floor(size) == 18:
                return "### " + s1['text']
            else:
                print("not handle this size line: %s" % size)
                return None
        else:
            return None
    return None


def check_is_table_or_figure_header(block):
    lines = block['lines']
    if len(lines) == 1:
        s1 = lines[0]['spans'][0]
        if s1['font'] == "Birka-Italic":
            tx = s1['text']
            if re.match(r"Table \d+-\d+.*", tx) is not None:
                return tx, 2
            if re.match(r"Figure \d+-\d+.*", tx) is not None:
                return "=    " + tx + "\n\n```\n\n\n\n\n```", 1
        else:
            return None, 0
    return None, 0


def get_normal_str_by_lines(lines):
    mdstr_outs = []
    for line in lines:
        for span in line['spans']:
            font = span['font']
            if font == "Birka" or font == "Symbol":
                mdstr_outs.append(str(span['text']))
            elif font == "TheSansMonoCondensed-Sem":
                mdstr_outs.append("`" + str(span['text']) + '`')
            elif font == "Birka-Italic":
                mdstr_outs.append("**" + str(span['text']).strip() + '**')
            else:
                print(get_line_texts(line), ": ")
                print("not support type span: %s" % str(span))
    return " ".join(mdstr_outs)


def get_normal_blocks_str(block):
    lines = block['lines']
    return get_normal_str_by_lines(lines)


def md_split_line(field_cnt):
    outs = ['|']
    for i in range(field_cnt):
        outs.append("---")
        outs.append("|")
    return "".join(outs)


def get_table_str_by_blocks(blocks):
    table_line_cnt = 1
    table_outs = []

    f_block = blocks[0]
    block_cnt = len(blocks)
    f_lines = f_block['lines']
    field_cnt = len(f_lines)
    x0_tb, y0_tb, x1_tb, y1_tb = f_block['bbox']
    f_str = get_block_texts(f_block, '|')
    table_outs.append("|" + f_str + "|")
    table_outs.append(md_split_line(field_cnt))

    for i in range(1, block_cnt):
        block = blocks[i]
        lines = block['lines']
        l_cnt = len(lines)
        x0, y0, x1, y1 = block['bbox']
        diff = abs(x0 - x0_tb)
        if diff > 0.6:
            break
        table_line_outs = ['|']

        if l_cnt == field_cnt:
            for line in lines:
                table_line_outs.append(get_line_texts(line))
                table_line_outs.append("|")
        elif l_cnt > field_cnt:
            j = 0
            j_end = 0
            fi = 0
            while j < l_cnt:
                line = lines[j]
                x0, y0, x1, y1 = line['bbox']
                if j == l_cnt - 1:
                    table_line_outs.append(get_line_texts(lines[j]))
                    table_line_outs.append("|")
                    j += 1
                    continue

                j_end = j
                x02, y02, x12, y12 = lines[j_end + 1]['bbox']
                while abs(x02 - x0) < 0.2:
                    j_end += 1
                    if j_end + 1 < l_cnt:
                        x02, y02, x12, y12 = lines[j_end + 1]['bbox']
                    else:
                        break
                table_line_outs.append(get_lines_texts(lines[j:j_end+1]))
                table_line_outs.append("|")
                j = j_end + 1
                continue
        else:
            print("line < fields..")
            sys.exit(-1)

        table_line_cnt += 1
        table_outs.append("".join(table_line_outs))

    return "\n".join(table_outs), table_line_cnt


class Book1ToMd:
    """
    本书格式：
    普通正文类型：
    'size': 10.199999809265137, 'flags': 4, 'font': 'Birka'
    代码类型 + 字段：
    'size': 9.180000305175781, 'flags': 4, 'font': 'TheSansMonoCondensed-Sem'
    四级标题：
    {'size': 11.536897659301758, 'flags': 20, 'font': 'Myriad-CnSemibold', 'color': 0
    三级标题：
    {'size': 15.732132911682129, 'flags': 20, 'font': 'Myriad-CnSemibold', 'color': 0
    二级标题：
    [{'size': 18.878559112548828, 'flags': 20, 'font': 'Myriad-CnSemibold', 'color': 0
    章节：
    {'size': 25.171411514282227, 'flags': 20, 'font': 'Myriad-CnSemibold', 'color': 0,
    斜体字：
    {'size': 10.199999809265137, 'flags': 6, 'font': 'Birka-Italic', 'color': 0
    """

    def __int__(self):
        pass

    def pages_to_md(self, index_s, count=1):
        page_outs = []
        for idx in range(index_s, index_s + count):
            page = doc[idx]
            tx_p = page.get_textpage()
            blocks = tx_p.extractDICT(sort=True)
            blocks = blocks['blocks']
            blocks_outs = []
            block_cnt = len(blocks)
            i = 0
            while i < block_cnt:
                if i > block_cnt - 2 - 1:  # 最后2块是页脚, 舍弃
                    break
                blk = blocks[i]
                lines = blk['lines']
                flag, code_line = check_is_code_blocks(blk)
                if flag:
                    if code_line < len(lines):
                        if code_line > 1:
                            blocks_outs.append(
                                "```c\n" + get_block_texts(blk, spl='\n', start_line=0, line_limit=code_line) + "\n```" +
                                "\n" + get_normal_str_by_lines(lines[code_line:]))
                        else:
                            blocks_outs.append(
                                "`" + get_block_texts(blk, spl='\n', start_line=0, line_limit=code_line) + "`" +
                                "\n" + get_normal_str_by_lines(lines[code_line:]))
                    else:
                        blocks_outs.append(
                            "```c\n" + get_block_texts(blk, spl='\n', start_line=0, line_limit=code_line) + "\n```")
                    i += 1
                    continue

                ret = check_title_blocks(blk)
                if ret is not None:
                    blocks_outs.append(ret)
                    i += 1
                    continue

                ret, tp = check_is_table_or_figure_header(blk)
                if tp == 1:  # figure
                    blocks_outs.append(ret)
                    i += 1
                    continue

                if tp == 2:  # table
                    out_str, line_cnt = get_table_str_by_blocks(blocks[i + 1:])
                    blocks_outs.append(ret)
                    blocks_outs.append(out_str)
                    i += line_cnt + 1
                    continue
                nstr = get_normal_blocks_str(blk)
                if nstr is not None and len(nstr) > 0:
                    blocks_outs.append(nstr)
                i += 1

            page_outs.extend(blocks_outs)
        out_str = "\n\n".join(page_outs)
        out_book1.write(out_str)
        pyperclip.copy(out_str)


b1 = Book1ToMd()
b1.pages_to_md(70, 1)
# get_pages_text(220)

out.close()
