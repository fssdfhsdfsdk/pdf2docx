import copy
import sys

import fitz
from pprint import pprint
import math
import re
import pyperclip

TYPE_FIGURE = 1
TYPE_TABLE = 2

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


def get_block_texts(block, span_spl: str, line_spl: str=None, start_line=None, line_limit=None):
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
        if line_spl is not None:
            line_outs = []
            for span in line['spans']:
                line_outs.append(span['text'])
            outs.append(span_spl.join(line_outs))
        else:
            for span in line['spans']:
                outs.append(span['text'])
        start_line += 1
    if line_spl is not None:
        return line_spl.join(outs)
    else:
        return span_spl.join(outs)


def md_split_line(field_cnt):
    outs = ['|']
    for i in range(field_cnt):
        outs.append("---")
        outs.append("|")
    return "".join(outs)


def check_sizes(configSzs, spanSz, size_diff):
    if isinstance(configSzs, list):
        for sz in configSzs:
            if abs(spanSz - sz) < size_diff:
                return True
        return False
    else:
        if abs(spanSz - configSzs) < size_diff:
            return True
        else:
            return False

def check_size_and_font(configFontDc, spanFontDc, size_diff=0.1):
    try:
        font = configFontDc['font']
        szs = configFontDc['size']
        if isinstance(font, list):
            if spanFontDc['font'] in font:
                return check_sizes(szs, spanFontDc['size'], size_diff)
        else:
            if spanFontDc['font'] == font:
                return check_sizes(szs, spanFontDc['size'], size_diff)
    except KeyError:
        return False

def code_block_check(codes: str):
    keywords = ["#include", "int", "main", "union", "struct", "char", "if", "else", "while", "sizeof", "short", "long"]
    for key in keywords:
        if codes.find(key) != -1:
            return True
    return False
def code_block_text_handle_remove_line_number(codes: str):
    outs = []
    if not code_block_check(codes):
        return codes

    for line in codes.splitlines():
        try:
            int(line.strip())
            continue  # 是一行数字, 丢弃
        except ValueError:
            pass

        spans = line.strip().split()
        try:
            int(spans[0].strip())
            outs.append(" ".join(spans[1:]))
            continue
        except ValueError:
            pass
        outs.append(line)
    return "\n".join(outs)


class BlocksWrapper:
    def __init__(self, blocks):
        if blocks is None:
            raise ValueError
        self.blocks = blocks
        if isinstance(blocks, list):
            self.cnt = len(blocks)
            self.block0 = blocks[0]
        else:
            self.cnt = 1
            self.block0 = blocks
        self._b0_l_cnt = None
        self._b0_l0_s_cnt = None
        self.block_idx = 0

    @property
    def block0_line_cnt(self):
        if self._b0_l_cnt is None:
            lines = self.block0['lines']
            self._b0_l_cnt = len(lines)
            spans = lines[0]['spans']
            self._b0_l0_s_cnt = len(spans)
        return self._b0_l_cnt

    @property
    def block0_line0_span_cnt(self):
        if self._b0_l0_s_cnt is None:
            cnt = self.block0_line_cnt
        return self._b0_l0_s_cnt

    def check_block0_single_span(self):
        """
        Ds: 检查某一个块是否只有一行, 且这一行只有一个span
        Return:
            符合, 则返回这个span的文本
            否则, 返回None, 表示不符合
        """
        if self.block0_line_cnt == 1 and self.block0_line0_span_cnt == 1:
            return get_block_texts(self.block0, " ")
        return None

    def get_current_block_and_inc_cursor(self, inc_idx=True):
        idx = self.block_idx
        if idx < self.cnt:
            if inc_idx:
                self.block_idx += 1
            return self.blocks[idx]
        else:
            return None

    def get_next_block_and_inc_cursor(self, inc_idx=True):
        """
        获取游标的下一个block
        """
        next_idx = self.block_idx + 1
        if next_idx < self.cnt:
            if inc_idx:
                self.block_idx += 1
            return self.blocks[next_idx]
        else:
            return None

    def inc_cursor(self):
        self.block_idx += 1

    def get_current_0line0span_font(self):
        if self.block_idx >= self.cnt:
            return {}
        blk = self.blocks[self.block_idx]
        s0 = blk['lines'][0]['spans'][0]
        return {'size': s0['size'], 'font': s0['font']}

class MdElement:
    def __init__(self, text, bbox):
        self.bbox = bbox
        self.text = text
        x0, y0, x1, y1 = bbox
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def __str__(self):
        return self.text


class CodeMixNormalBlock:
    def __init__(self, book_config: dict):
        self.bookCfg = book_config
        if "codeHandle" in book_config.keys():
            self.code_text_handle = globals()[book_config["codeHandle"]]
        else:
            self.code_text_handle = None

        self.code_block_prefix = "```" + self.bookCfg['language']
        self.code_block_suffix = "```"

        self.md_outs = []
        self.prefix_idx = -1
        self.suffix_idx = -1

    def append_outs(self, line):
        self.md_outs.append(line)

    def set_header_prefix(self):
        self.prefix_idx = len(self.md_outs)
        self.md_outs.append(self.code_block_prefix)

    def set_end_suffix(self):
        self.suffix_idx = len(self.md_outs)
        self.md_outs.append(self.code_block_suffix)

    @property
    def codeblock(self):
        normal_code = "\n".join(self.md_outs[self.prefix_idx+1:self.suffix_idx])
        if self.code_text_handle is not None:
            return self.code_text_handle(normal_code)
        else:
            return normal_code

    def __str__(self):
        outs = []
        if self.suffix_idx <= self.prefix_idx:
            return "\n".join(self.md_outs)
        outs.extend(self.md_outs[0:self.prefix_idx+1])
        outs.append(self.codeblock)
        outs.extend(self.md_outs[self.suffix_idx:])

        return "\n".join(outs)


class Book2ToMd:

    def __init__(self, book_config: dict):
        self.bookCfg = book_config
        self.docs = fitz.open(self.bookCfg['path'])  # open a document
        self.blockquoteCfg = copy.deepcopy(book_config)  # 必须深度copy, 不然有嵌套dict还是会有问题
        self.blockquoteCfg['normal']['size'] = self.blockquoteCfg['blockquote']['size']
        self.blockquoteCfg['italic']['size'] = self.blockquoteCfg['blockquote']['size']
        self.blockquoteCfg['inline-code']['size'] = self.blockquoteCfg['blockquote']['size']



    def check_size_and_font_by_config(self, f1, keys, size_diff=0.1):
        return check_size_and_font(self.bookCfg[keys], f1, size_diff)

    def check_is_code_blocks(self, block):
        flag = False
        code_line = 0
        for line in block['lines']:
            spans = line['spans']
            if len(spans) == 1 and spans[0]['font'] == self.bookCfg['codeblock']['font']:
                flag = True
                code_line += 1
        return flag, code_line

    def append_outs_mixed_noraml_and_codeblock(self, cn_block: CodeMixNormalBlock, blk, lines, cline_start, cline_cnt,
                                               need_start=True, need_ends=True):
        if lines == 1:
            cn_block.append_outs("`" + get_block_texts(blk, span_spl=' ', line_spl='\n', start_line=0, line_limit=cline_cnt) + "`")
            str_out = self.get_normal_str_by_lines(self.bookCfg, lines[cline_cnt:])
            if str_out != '':
                cn_block.append_outs(str_out)
        else:
            str_out = self.get_normal_str_by_lines(self.bookCfg, lines[0:cline_start])
            if str_out != '':
                cn_block.append_outs(str_out)

            if need_start:
                cn_block.set_header_prefix()
            cn_block.append_outs(get_block_texts(blk, span_spl=' ', line_spl='\n', start_line=cline_start, line_limit=cline_cnt))
            if need_ends:
                cn_block.set_end_suffix()
            str_out = self.get_normal_str_by_lines(self.bookCfg, lines[cline_start + cline_cnt:])
            if str_out != '':
                cn_block.append_outs(str_out)

    def check_code_blocks(self, blocks, code_one_span=False):
        """
        参数:
         code_one_span: True限制代码行, 只能有一个span
        场景:
         第一个block:
           1、全是代码
           2、开头一行代码 + 文本
           3、开头多行代码 + 文本
           4、中间n行存在代码 (不处理)
         第二个block: 第一个block是类型1 && 递归处理
           与上一个block在 y轴上相近, 且是类型1...
        """
        wp = BlocksWrapper(blocks)
        b_cnt = 0
        blk = wp.get_current_block_and_inc_cursor()

        code_mixed = CodeMixNormalBlock(self.bookCfg)
        while blk is not None:
            code_line = 0
            lines = blk['lines']
            l_cnt = len(lines)
            cline_start = -1
            for j in range(l_cnt):
                line = lines[j]
                spans = line['spans']
                if code_one_span and len(spans) != 1:
                    break

                if self.check_size_and_font_by_config(spans[0], 'codeblock'):
                    code_line += 1
                    if cline_start == -1:
                        cline_start = j
            # if code_line > 0:
            #     print("code lines: ", code_line, ", start line: ", cline_start, ", line_cnt: ", l_cnt)

            if b_cnt == 0:
                b_cnt += 1
                if code_line == 0:
                    return None, 0
                elif code_line < l_cnt and cline_start == 0:
                    #  如果块的代码行数 小于 块的行数, 则说明下一个块与此块 代码不连续. 直接填充返回
                    self.append_outs_mixed_noraml_and_codeblock(code_mixed, blk, lines, cline_start, code_line)
                    break
                else:
                    self.append_outs_mixed_noraml_and_codeblock(code_mixed, blk, lines, cline_start,
                                                                code_line, need_start=True, need_ends=False)
            else:
                if code_line == 0:
                    break
                elif code_line < l_cnt and cline_start == 0:
                    self.append_outs_mixed_noraml_and_codeblock(code_mixed, blk, lines, cline_start,
                                                                code_line, need_start=False, need_ends=True)
                    break
                else:
                    b_cnt += 1
                    self.append_outs_mixed_noraml_and_codeblock(code_mixed, blk, lines, cline_start,
                                                                code_line, need_start=False, need_ends=False)
            blk = wp.get_current_block_and_inc_cursor()
        if code_mixed.prefix_idx != -1 and code_mixed.suffix_idx == -1:
            code_mixed.set_end_suffix()

        return str(code_mixed), b_cnt

    def getMdTitlePrefixBySpan(self, span):
        if self.check_size_and_font_by_config(span, 'title-3'):
            return "### "
        elif self.check_size_and_font_by_config(span, 'title-4'):
            return "#### "
        elif self.check_size_and_font_by_config(span, 'title-5'):
            return "##### "
        else:
            return ""

    def check_title_blocks(self, block):
        """
        缺陷:
            1、长标题跨2行而成为2个block无法识别
        """
        lines = block['lines']
        l_cnt = len(lines)

        if l_cnt < 3:
            s1 = lines[0]['spans'][0]
            lv_prefix = self.getMdTitlePrefixBySpan(s1)
            if lv_prefix == "":
                return None

            if l_cnt == 2:
                s2 = lines[1]['spans'][0]
                if self.getMdTitlePrefixBySpan(s2) == "":
                    return None

            if l_cnt == 3:
                s2 = lines[2]['spans'][0]
                if self.getMdTitlePrefixBySpan(s2) == "":
                    return None

            return lv_prefix + get_lines_texts(lines)
        else:
            return None

    def check_table_or_figure_title(self, blocks, flag):
        """
         描述: 布局由 表标题 + 表体组成
           表标题由特殊字符的span开头, 表标题由一行或多行组成, 暂时按同span处理
           表体的每一表行由多个cell组成, cell由多行对齐 , 每一表行的x轴对齐
         缺陷:
           1、 判断表格出现的方式依赖与 Table xx的span格式, 若与正文相同则误判
           2、 复杂表体布局不支持, cell
           3、 表格跨页, 不支持
           4、 跨多行cell不支持
         layout:
           Table xx-xx yyyyyyyyyyyy
           ???? yyyyyyyyy
           ...
            cell    cell   cell ...
            ---     ---    ---
                    ---
            cell    cell   cell ...
            ---     ---    ---
            ---
           ....

        """
        if flag != TYPE_FIGURE and flag != TYPE_TABLE:
            raise ValueError

        if not blocks:
            return None, 0

        if flag == TYPE_FIGURE:
            font = self.bookCfg['table_or_figure']['font'] if self.bookCfg['table_or_figure'] != {} \
                else self.bookCfg['figure']['font']
        else:
            font = self.bookCfg['table_or_figure']['font'] if self.bookCfg['table_or_figure'] != {} \
                else self.bookCfg['table']['font']
        b_len = len(blocks)
        for i in range(1):
            block = blocks[i]
            lines = block['lines']
            l0 = lines[0]
            spans = l0['spans']
            s0 = spans[0]
            if flag == TYPE_FIGURE:
                re_str = r"\s*Figure \d+[\-\.]\d+.*"
            else:
                re_str = r"\s*Table \d+[\-\.]\d+.*"

            if s0['font'] != font or re.match(re_str, s0['text']) is None:
                return None, 0
            else:
                if i == b_len - 1:
                    if flag == TYPE_FIGURE:
                        return get_lines_texts(lines) + "\n\n```\n\n\n\n\n```", 1
                    else:
                        return get_lines_texts(lines) , 1
                else:
                    x0, y0, x1, y1 = block['bbox']
                    next_blk = blocks[i + 1]
                    x20, y20, x21, y21 = next_blk['bbox']
                    # 段落首行缩进分为2个block, 合并为1个
                    if abs(x20 - x0) > 15 and abs(y20 - y0) < 15:
                        if flag == TYPE_FIGURE:
                            return get_lines_texts(lines) + " " + get_block_texts(next_blk, " ") \
                                   + "\n\n```\n\n\n\n\n```", 2
                        else:
                            return get_lines_texts(lines) + " " + get_block_texts(next_blk, " "), 2
                    else:
                        if flag == TYPE_FIGURE:
                            return get_lines_texts(lines) + "\n\n```\n\n```", 1
                        else:
                            return get_lines_texts(lines), 1
        return None, 0

    def check_table_title(self, blocks):
        return self.check_table_or_figure_title(blocks, TYPE_TABLE)

    def check_figure_title(self, blocks):
        return self.check_table_or_figure_title(blocks, TYPE_FIGURE)

    def check_block_quote_by_keyword(self, blocks, keyword):
        wp = BlocksWrapper(blocks)
        md_outs = ["> " + keyword, "> "]
        if wp.check_block0_single_span() == keyword:
            next_blk = wp.get_next_block_and_inc_cursor()
            f2 = wp.get_current_0line0span_font()
            if not check_size_and_font(self.bookCfg['blockquote'], f2):
                return None, 0
            if next_blk is not None:
                md_outs.append("> " + get_block_texts(next_blk, span_spl=" "))
                return "\n".join(md_outs), 2
        return None, 0

    def check_block_quote_by_font(self, blocks):
        wp = BlocksWrapper(blocks)
        md_outs = []
        f2 = wp.get_current_0line0span_font()
        if not check_size_and_font(self.bookCfg['blockquote'], f2):
            return None, 0

        cur_blk = wp.get_current_block_and_inc_cursor()
        b_cnt = 0
        while cur_blk is not None:
            if b_cnt == 0:
                md_outs.append("> " + self.get_normal_blocks_str(cur_blk, self.blockquoteCfg))
            else:
                md_outs.append("> ")
                md_outs.append("> " + self.get_normal_blocks_str(cur_blk, self.blockquoteCfg))
            b_cnt += 1

            cur_blk = wp.get_current_block_and_inc_cursor(inc_idx=False)
            f2 = wp.get_current_0line0span_font()
            if not check_size_and_font(self.bookCfg['blockquote'], f2):
                cur_blk = None
            wp.inc_cursor()

        if b_cnt > 0:
            print("block quote cnt:", b_cnt)
            return "\n".join(md_outs), b_cnt
        return None, 0

    def get_normal_str_by_lines(self, nm_dc_font_dc, lines):
        mdstr_outs = []

        pre_line_end_str = None
        len_cnt = len(lines)
        for j in range(len_cnt):
            line = lines[j]
            spans = line['spans']
            cnt = len(spans)
            for i in range(cnt):
                span = spans[i]
                font = span['font']
                if check_size_and_font(nm_dc_font_dc['normal'], span) or font == "Symbol":
                    tx = span['text']
                    tx_len = len(tx)
                    # 去除段落的 跨行 单词: leng- \n th ==> length
                    if i == cnt - 1 and tx_len > 1 and tx.endswith("-") and j != len_cnt - 1:
                        tmp_str = tx[0:tx_len - 1]
                        if i == 0 and pre_line_end_str is not None:
                            pre_line_end_str += tmp_str
                        else:
                            pre_line_end_str = tmp_str
                    elif i == 0 and pre_line_end_str is not None:
                        mdstr_outs.append(pre_line_end_str + tx)
                        pre_line_end_str = None
                    else:
                        mdstr_outs.append(tx)
                elif check_size_and_font(nm_dc_font_dc['inline-code'], span):
                    mdstr_outs.append("`" + str(span['text']) + '`')
                elif check_size_and_font(nm_dc_font_dc['italic'], span):
                    mdstr_outs.append("**" + str(span['text']).strip() + '**')
                else:
                    print("one line [ %s ]" % get_line_texts(line))
                    try:
                        print("not support type span: %s" % str(span))
                    except TypeError as e:
                        raise e
        return " ".join(mdstr_outs)

    def get_normal_blocks_str(self, block, nm_dc_font_dc=None):
        lines = block['lines']
        if nm_dc_font_dc is None:
            nm_dc_font_dc = self.bookCfg
        return self.get_normal_str_by_lines(nm_dc_font_dc, lines)

    @DeprecationWarning
    def get_table_str_by_blocks(self, blocks):
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
                    table_line_outs.append(get_lines_texts(lines[j:j_end + 1]))
                    table_line_outs.append("|")
                    j = j_end + 1
                    continue
            else:
                print("line < fields..")
                sys.exit(-1)

            table_line_cnt += 1
            table_outs.append("".join(table_line_outs))

        return "\n".join(table_outs), table_line_cnt

    def tableListList2Md(self, tb_ll, row_count, col_count):
        outs = []
        for i in range(row_count):
            for j in range(col_count):
                if tb_ll[i][j] is None:
                    tb_ll[i][j] = ""
                    continue
                if tb_ll[i][j].find("\n") != -1:
                    tb_ll[i][j] = tb_ll[i][j].replace("\n", " ")

        for i in range(row_count):
            outs.append("|" + "|".join(tb_ll[i]))
            if i == 0:
                outs.append(md_split_line(col_count))
        return "\n".join(outs)

    def filter_blocks_by_bbox(self, blocks, invalid_bbox):
        """
        将所有在一个方框内的block过滤掉
        """
        ix0, iy0, ix1, iy1 = invalid_bbox
        out_blocks = []
        for block in blocks:
            x0, y0, x1, y1 = block['bbox']
            if y0 > iy0 and x0 > ix0 and ix1 > x1 and iy1 > y1:
                pass
            else:
                out_blocks.append(block)
        return out_blocks

    def configOfBlockQueto(self):
        if 'blockquote-type' not in self.bookCfg.keys():
            return "keyword"
        else:
            return "font"

    def pages_to_md(self, index_s, count=1):
        page_outs = []
        for idx in range(index_s, index_s + count):
            page = self.docs[idx]
            tx_p = page.get_textpage()
            blocks = tx_p.extractDICT(sort=True)
            blocks = blocks['blocks']
            md_elements = []

            tables = page.find_tables()
            tables = tables.tables

            for tb in tables:
                tb_ll = tb.extract()
                if tb_ll[0][0] is None:
                    continue
                table_md_str = self.tableListList2Md(tb_ll, tb.row_count, tb.col_count)
                blocks = self.filter_blocks_by_bbox(blocks, tb.bbox)
                md_elements.append(MdElement(table_md_str, tb.bbox))

            block_cnt = len(blocks)
            i = 0
            while i < block_cnt:
                if i < self.bookCfg['header_block_cnt']:
                    i += 1
                    continue
                if i > block_cnt - self.bookCfg['footer_block_cnt'] - 1:
                    break
                blk = blocks[i]
                bbox = blk['bbox']

                ret, tmp_b_cnt = self.check_code_blocks(blocks[i:])
                if ret is not None:
                    md_elements.append(MdElement(ret, bbox))
                    i += tmp_b_cnt
                    continue

                # 关键字 可能被当做标题
                if self.configOfBlockQueto() == "keyword":
                    ret, tmp_b_cnt = self.check_block_quote_by_keyword(blocks[i:], keyword="Note")
                else:
                    ret, tmp_b_cnt = self.check_block_quote_by_font(blocks[i:])
                if ret is not None:
                    md_elements.append(MdElement(ret, bbox))
                    i += tmp_b_cnt
                    continue

                ret = self.check_title_blocks(blk)
                if ret is not None:
                    md_elements.append(MdElement(ret, bbox))
                    i += 1
                    continue

                ret, tmp_b_cnt = self.check_figure_title(blocks[i:])
                if ret is not None:
                    md_elements.append(MdElement(ret, bbox))
                    i += tmp_b_cnt
                    continue

                ret, tmp_b_cnt = self.check_table_title(blocks[i:])
                if ret is not None:
                    md_elements.append(MdElement(ret, bbox))
                    i += tmp_b_cnt
                    continue

                if i < block_cnt - 1:
                    x0, y0, x1, y1 = blk['bbox']
                    next_blk = blocks[i + 1]
                    next_l_cnt = len(next_blk['lines'])
                    x20, y20, x21, y21 = next_blk['bbox']

                    if next_l_cnt == 1:
                        x1_diff = x1 - x0 - (x21 - x20)
                    else:
                        x1_diff = 4

                    # 段落首行缩进分为2个block, 合并为1个
                    if abs(x20 - x0) > 10 and abs(y20 - y0) < 15 and abs(x21 - x1) < x1_diff:
                        for line in blk['lines']:
                            next_blk['lines'].insert(0, line)
                        i += 1
                        continue

                md_str = self.get_normal_blocks_str(blk)
                if md_str is not None and len(md_str) > 0:
                    md_elements.append(MdElement(md_str, bbox))
                i += 1
            md_elements = sorted(md_elements, key=lambda x: x.y0)
            page_outs.extend(md_elements)
        out_str = "\n\n".join(map(str, page_outs))
        # out_book1.write(out_str)
        pyperclip.copy(out_str)


"""
 todo list:
   1、自动跳过header footer
"""
book1ConfigDc = {
    'header_block_cnt': 1,  # 页眉 块数 跳过
    'footer_block_cnt': 0,  # 页脚 块数 跳过
    'path': r"H:\pdf\CS计算机\网络\TCPIP Illustrated, Volume 1 The Protocols by Kevin R. Fall, W. Richard Stevens (z-lib.org).pdf",

    'normal': {'size': 10.0, 'flags': 4, 'font': ['Palatino-Roman', 'Courier-Oblique', 'Palatino-Bold', 'Palatino-BoldItalic']},  # 正文 格式
    'italic': {'size': 10.0, 'flags': 6, 'font': 'Palatino-Italic'},  # 正文 斜体字格式 ==> md加粗 *xxx*
    'inline-code': {'size': 10.0, 'flags': 4, 'font': 'Courier'},  # 正文 内联代码块  ==>  `xxx`

    'codeblock': {'size': 8.0, 'flags': 20, 'font': ['Courier-Bold', 'Courier', 'Courier-Oblique', 'Palatino-Italic']},  # 代码块
    'language': "",  # 代码块的默认编程语言

    'title-5': {'size': 10.0, 'flags': 20, 'font': 'Helvetica-Oblique'},
    'title-4': {'size': 10.0, 'flags': 20, 'font': 'Helvetica-Bold'},
    'title-3': {'size': 13.0, 'flags': 20, 'font': 'Helvetica-Bold'},  # md 3级标题
    'chapter': {},  # 章节名 ===> md 2级标题(不支持)

    'blockquote': {'size': 9.0, 'flags': 4, 'font': 'Helvetica'},  # md的 > xxxx 的块引用格式

    # 第一个为{}, 则要填后面2个, 否则2个格式相同 都用第一个
    'table_or_figure': {'size': 8.0, 'flags': 20, 'font': 'Palatino-Bold'},
    'table': {},
    'figure': {},
}


book1ConfigDc2 = {
    'header_block_cnt': 1,  # 页眉 块数 跳过
    'footer_block_cnt': 0,  # 页脚 块数 跳过
    'path': r"H:\pdf\CS计算机\网络\UNIX Network Programming, Volume 1 The Sockets Networking API, 3rd Edition (W. Richard Stevens, Bill Fenner etc.) (z-lib.org).pdf",

    'normal': {'size': [11.14, 10.03], 'flags': 4, 'font': ['Palatino-Roman']},  # 正文 格式
    'italic': {'size': [11.14, 10.03, 7.8], 'flags': 6, 'font': ['Palatino-Italic', 'Palatino-Bold',
                                                                 'Courier-Bold', 'Courier-Oblique']},  # 正文 斜体字格式 ==> md加粗 *xxx*
    'inline-code': {'size': [11.14], 'flags': 4, 'font': 'Courier'},  # 正文 内联代码块  ==>  `xxx`

    'codeblock': {'size': 9.08, 'flags': 20, 'font': ['Courier-Bold', 'Courier', 'Courier-Oblique', 'Palatino-Italic', 'Palatino-Roman']},  # 代码块
    'language': "c",  # 代码块的默认编程语言
    'codeHandle': "code_block_text_handle_remove_line_number",  # 代码块文本处理函数

    'title-5': {'size': 10.0, 'flags': 20, 'font': 'Helvetica-Oblique'},
    'title-4': {'size': 11.14, 'flags': 20, 'font': 'Helvetica-Bold'},
    'title-3': {'size': 13.37, 'flags': 20, 'font': ['Helvetica-Bold', 'Courier-Bold']},  # md 3级标题
    'chapter': {},  # 章节名 ===> md 2级标题(不支持)

    'blockquote': {'size': 8.9, 'flags': 4, 'font': 'Palatino-Roman'},  # md的 > xxxx 的块引用格式
    'blockquote-type': "",   # 默认关键词触发

    # 第一个为{}, 则要填后面2个, 否则2个格式相同 都用第一个
    'table_or_figure': {'size': 8.91, 'flags': 20, 'font': 'Palatino-Bold'},
    'table': {},
    'figure': {},
}


if __name__ == "__main__":
    b1 = Book2ToMd(book1ConfigDc2)
    b1.pages_to_md(118, 1)
