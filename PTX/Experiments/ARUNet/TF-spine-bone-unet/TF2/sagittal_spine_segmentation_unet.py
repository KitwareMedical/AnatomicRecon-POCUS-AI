# U-Net Model Construction

import unittest

import numpy as np

import tensorflow as tf
from tensorflow.keras.models import *
from tensorflow.keras.layers import *
from tensorflow.keras.optimizers import *
from tensorflow.keras.regularizers import l1, l2

from tensorflow.keras import backend as K


def sagittal_spine_unet(input_size, num_classes, filter_multiplier=10, regularization_rate=0.):
    input_ = Input((input_size, input_size, 1))
    skips = []
    output = input_

    num_layers = int(np.floor(np.log2(input_size)))
    down_conv_kernel_sizes = np.zeros([num_layers], dtype=int)
    down_filter_numbers = np.zeros([num_layers], dtype=int)
    up_conv_kernel_sizes = np.zeros([num_layers], dtype=int)
    up_filter_numbers = np.zeros([num_layers], dtype=int)

    for layer_index in range(num_layers):
        down_conv_kernel_sizes[layer_index] = int(3)
        down_filter_numbers[layer_index] = int((layer_index + 1) * filter_multiplier + num_classes)
        up_conv_kernel_sizes[layer_index] = int(4)
        up_filter_numbers[layer_index] = int((num_layers - layer_index - 1) * filter_multiplier + num_classes)

    for shape, filters in zip(down_conv_kernel_sizes, down_filter_numbers):
        skips.append(output)
        output = Conv2D(filters, (shape, shape), strides=2, padding="same", activation="relu",
                        bias_regularizer=l1(regularization_rate))(output)

    for shape, filters in zip(up_conv_kernel_sizes, up_filter_numbers):
        output = tf.keras.layers.UpSampling2D()(output)
        skip_output = skips.pop()
        output = concatenate([output, skip_output], axis=3)
        if filters != num_classes:
            output = Conv2D(filters, (shape, shape), activation="relu", padding="same",
                            bias_regularizer=l1(regularization_rate))(output)
            output = BatchNormalization(momentum=.9)(output)
        else:
            output = Conv2D(filters, (shape, shape), activation="softmax", padding="same",
                            bias_regularizer=l1(regularization_rate))(output)

    assert len(skips) == 0
    return Model([input_], [output])


def dice_coef(y_true, y_pred, smooth=1):
    """
    Dice = (2*|X & Y|)/ (|X|+ |Y|)
         =  2*sum(|A*B|)/(sum(A^2)+sum(B^2))
    ref: https://arxiv.org/pdf/1606.04797v1.pdf
    """
    intersection = K.sum(K.abs(y_true * y_pred), axis=-1)

    return (2. * intersection + smooth) / (K.sum(K.square(y_true), -1) + K.sum(K.square(y_pred), -1) + smooth)


def weighted_categorical_crossentropy(weights):
    """
    A weighted version of tf.keras.objectives.categorical_crossentropy

    Variables:
        weights: numpy array of shape (C,) where C is the number of classes
    """
    weights = K.variable(weights)

    def loss(y_true, y_pred):
        # scale predictions so that the class probas of each sample sum to 1
        y_pred /= K.sum(y_pred, axis=-1, keepdims=True)
        # clip to prevent NaN's and Inf's
        y_pred = K.clip(y_pred, K.epsilon(), 1 - K.epsilon())
        # calc
        loss = y_true * K.log(y_pred) * weights
        loss = -K.sum(loss, -1)

        return loss

    return loss


class SagittalSpineUnetTest(unittest.TestCase):
    def test_create_model(self):
        model = sagittal_spine_unet(128, 2)

if __name__ == '__main__':
    unittest.main()
