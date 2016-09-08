"""
Domain-specific natural Language and bash command tokenizer.
"""

# builtin
from __future__ import print_function

import re
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))

import bash, normalizer
import gazetteer, spell_check

from nltk.stem.wordnet import WordNetLemmatizer
lmtzr = WordNetLemmatizer()

# Regular expressions used to tokenize an English sentence.
_WORD_SPLIT = re.compile(b"^\s+|\s*,\s*|\s+$|^[\(|\[|\{|\<]|[\)|\]|\}|\>]$")
_WORD_SPLIT_RESPECT_QUOTES = re.compile(b'(?:[^\s,"]|"(?:\\.|[^"])*")+')

_SPACE = b"<SPACE>"

def is_stopword(w):
    return w in gazetteer.ENGLISH_STOPWORDS

def char_tokenizer(sentence, base_tokenizer=None, normalize_digits=False,
                   normalize_long_pattern=False):
    if base_tokenizer:
        tokens = base_tokenizer(sentence, normalize_digits=False,
                                normalize_long_pattern=False)
    else:
        tokens = [sentence]
    chars = []
    for token in tokens:
        for c in token:
            chars.append(c)
        chars.append(_SPACE)
    return chars[:-1]

def basic_tokenizer(sentence, lower_case=True, normalize_digits=True, normalize_long_pattern=True,
                    lemmatization=True, remove_stop_words=True):
    """Very basic tokenizer: used for English tokenization."""
    sentence = sentence.replace('`\'', '"') \
            .replace('``', '"') \
            .replace("''", '"') \
            .replace(' \'', ' "') \
            .replace('\' ', '" ') \
            .replace('`', '"') \
            .replace('(', '( ') \
            .replace(')', ' )')
            # .replace('[', '[ ') \
            # .replace('{', '{ ') \
            # .replace(']', ' ]') \
            # .replace('}', ' }') \
            # .replace('<', '< ') \
            # .replace('>', ' >')
    sentence = re.sub('^\'', '"', sentence)
    sentence = re.sub('\'$', '"', sentence)

    sentence = re.sub('(,\s+)|(,$)', ' ', sentence)
    sentence = re.sub('(;\s+)|(;$)', ' ', sentence)
    sentence = re.sub('(:\s+)|(:$)', ' ', sentence)
    sentence = re.sub('(\.\s+)|(\.$)', ' ', sentence)

    sentence = re.sub('\'s', '\\\'s', sentence)
    sentence = re.sub('\'re', '\\\'re', sentence)
    sentence = re.sub('\'ve', '\\\'ve', sentence)
    sentence = re.sub('\'d', '\\\'d', sentence)
    sentence = re.sub('\'t', '\\\'t', sentence)

    words = re.findall(_WORD_SPLIT_RESPECT_QUOTES, sentence)

    normalized_words = []
    for i in xrange(len(words)):
        word = words[i].strip()

        # remove unnecessary upper cases
        if lower_case:
            if len(word) > 1 and word[0].isupper() and word[1:].islower():
                word = word.lower()

        # lemmatization
        if lemmatization:
            word = lmtzr.lemmatize(word)

        # spelling correction
        if word.isalpha():
            old_w = word
            word = spell_check.correction(word)
            if word != old_w:
                print("spell correction: {} -> {}".format(old_w, word))

        # remove English stopwords
        if remove_stop_words:
            if word in gazetteer.ENGLISH_STOPWORDS:
                continue

        # covert number words into numbers
        if word in gazetteer.word2num:
            word = str(gazetteer.word2num[word])

        # normalize regular expressions
        if not bash.is_english_word(word):
            # msg = word + ' -> '
            if not word.startswith('"'):
                word = '"' + word
            if not word.endswith('"'):
                word = word + '"'
            # msg += word
            # print(msg)

        # normalize long patterns
        if ' ' in word and len(word) > 3:
            try:
                assert(word.startswith('"') and word.endswith('"'))
            except AssertionError, e:
                print("Quotation Error: space inside word " + sentence)
            if normalize_long_pattern:
                word = bash._LONG_PATTERN

        # normalize digits
        word = re.sub(bash._DIGIT_RE, bash._NUM, word) \
            if normalize_digits and not word.startswith("-") else word

        # convert possessive expression
        if word.endswith("'s"):
            normalized_words.append(word[:-2])
            normalized_words.append("'s")
        else:
            normalized_words.append(word)

    return normalized_words


def bash_tokenizer(cmd, normalize_digits=True, normalize_long_pattern=True,
                   recover_quotation=True):
    tree = normalizer.normalize_ast(cmd, normalize_digits, normalize_long_pattern,
                         recover_quotation)
    return normalizer.to_tokens(tree)


def bash_parser(cmd, normalize_digits=True, normalize_long_pattern=True,
                recover_quotation=True):
    """Parse bash command into AST."""
    return normalizer.normalize_ast(cmd, normalize_digits, normalize_long_pattern,
                                    recover_quotation)


def pretty_print(node, depth=0):
    """Pretty print the AST."""
    try:
        print("    " * depth + node.kind.upper() + '(' + node.value + ')')
        for child in node.children:
            pretty_print(child, depth+1)
    except AttributeError, e:
        print("    " * depth)


def ast2list(node, order='dfs', list=None):
    """Linearize the AST."""
    if order == 'dfs':
        list.append(node.symbol)
        for child in node.children:
            ast2list(child, order, list)
        list.append("<NO_EXPAND>")
    return list


def list2ast(list, order='dfs'):
    """Convert the linearized parse tree back to the AST data structure."""
    return normalizer.list_to_ast(list, order)


def ast2tokens(node, loose_constraints=False, ignore_flag_order=False):
    return normalizer.to_tokens(node, loose_constraints, ignore_flag_order)


def ast2command(node, loose_constraints=False, ignore_flag_order=False):
    return ' '.join(normalizer.to_tokens(node, loose_constraints, ignore_flag_order))


def ast2template(node, loose_constraints=False, arg_type_only=True):
    # convert a bash AST to a template that contains only reserved words and argument types
    # flags are alphabetically ordered
    tokens = normalizer.to_tokens(node, loose_constraints, ignore_flag_order=True,
                                  arg_type_only=arg_type_only)
    return ' '.join(tokens)


def cmd2template(cmd, normalize_digits=True, normalize_long_pattern=True,
                recover_quotation=True, arg_type_only=True,
                loose_constraints=False):
    # convert a bash command to a template that contains only reserved words and argument types
    # flags are alphabetically ordered
    tree = normalizer.normalize_ast(cmd, normalize_digits, normalize_long_pattern,
                         recover_quotation)
    return ast2template(tree, loose_constraints, arg_type_only)


if __name__ == "__main__":
    while True:
        try:
            cmd = raw_input("Bash command: ")
            norm_tree = bash_parser(cmd)
            print()
            print("AST:")
            pretty_print(norm_tree, 0)
            # print(to_command(norm_tree))
            search_history = ast2list(norm_tree, 'dfs', [])
            # print(list)
            tree = list2ast(search_history + ['<PAD>'])
            # pretty_print(tree, 0)
            # print(to_template(tree, arg_type_only=False))
            print()
            print("Command Template (flags in alphabetical order):")
            print(ast2template(norm_tree))
            print()
        except EOFError as ex:
            break


