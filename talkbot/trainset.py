# ------- requirements ------
#
# click>=6.7,<7
# scikit-learn>=0.18.2,<0.19
# numpy>=1.13.1,<1.14
# scipy>=0.19.1,0.20
# ImageHash>=3.4
# pandas>=0.20.3,<0.21

import itertools
import multiprocessing
import operator
import os

from functools import reduce
from multiprocessing.pool import Pool

import click

import pandas as pd
import time

from PIL import Image
from catboost import CatBoostClassifier

from talkbot.utils import calc_scores, get_diff_vector, ALG, prepare_image

BASEDIR = './data'
TRAINDIR = os.path.join(BASEDIR, 'train')
RESHAPE = (512, 512)
pool_size = multiprocessing.cpu_count()


@click.group()
def _main():
    pass


def save_training_sampl(image_path, idx, sample_options):
    try:
        image_obj = Image.open(image_path)
        v, h, fit_image = sample_options[1:]
        name = '_%s_%s_%s_%s' % sample_options
        var_img = prepare_image(
            image_obj,
            crop_width_perc=v,
            crop_height_perc=h,
            fit_image=fit_image,
            grayscale=False
        )
        var_img.save(os.path.join(TRAINDIR, str(idx) + name + '.png'), 'PNG')

    except OSError as ex:
        print(ex)


def get_images_diff_vectors(image_pair):
    img_objs = map(lambda i: Image.open(os.path.join(TRAINDIR, i)), image_pair)
    scores = map(dict,
                 map(calc_scores, img_objs))

    names = [i.split('_')[0] for i in image_pair]
    is_dup = reduce(operator.eq, names)

    vector = get_diff_vector(*scores)
    vector['d'] = is_dup
    return vector


@_main.command()
def gen_set():
    img_files = [files for _, _, files in os.walk(BASEDIR)]

    with Pool(processes=pool_size) as pool:
        for idx, image in enumerate(img_files):
            image_path = os.path.join(BASEDIR, image)
            for sample_options in ALG:
                pool.apply(save_training_sampl, (image_path, idx, sample_options))


@_main.command()
@click.option('--out', default='sample.csv')
def store_training(out):
    start = time.time()
    img_files = [files for _, _, files in os.walk(TRAINDIR)]
    train_combs = itertools.combinations(img_files, 2)

    with Pool(processes=pool_size) as pool:
        vectors = pool.map(get_images_diff_vectors, train_combs)
    df = pd.DataFrame(vectors)
    df.to_csv(out, index=False)
    finished = time.time() - start
    click.echo("Finised in %s seconds" % finished)


@_main.command()
@click.option('--input', default='sample.csv')
def train(input):
    df = pd.read_csv(input)
    # convert values to bool
    df['d'] = df['d'].astype('bool')

    l_model = CatBoostClassifier()
    l_model = l_model.fit(
        df[df.columns.difference(['d'])],
        df['d']
    )

    images = ['3.png', '5.png']
    img_objs = map(lambda i: Image.open(os.path.join(BASEDIR, i)), images)
    scores = map(dict, map(calc_scores, img_objs))

    vector = get_diff_vector(*scores)

    print(vector)
    df2 = pd.DataFrame.from_dict([vector])
    # print(df2.values)

    p_class = l_model.predict(df2)[0]
    class_prob = l_model.predict_proba(df2)[0][int(p_class)]
    print(bool(int(p_class)), class_prob)


if __name__ == '__main__':
    _main()
