#!/usr/bin/env python
from __future__ import division, unicode_literals
import argparse

from onmt.translate.TranslatorMultimodal import make_translator

import onmt.io
import onmt.translate
import onmt
import onmt.ModelConstructor
import onmt.modules
import onmt.opts
import numpy as np


def main(opt):
    translator = make_translator(opt, report_score=True)
    test_img_feats = np.load(opt.path_to_test_img_feats)
    test_img_feats = test_img_feats.astype(np.float32)
    translator.translate(opt.src_dir, opt.src, opt.tgt,
                         opt.batch_size, opt.attn_debug,
                         test_img_feats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='translate_mmod_finetune.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    onmt.opts.add_md_help_argument(parser)
    onmt.opts.translate_opts(parser)
    onmt.opts.mmod_finetune_translate_opts(parser)

    opt = parser.parse_args()
    main(opt)
