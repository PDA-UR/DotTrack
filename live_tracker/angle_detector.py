import tensorflow as tf
from tensorflow import keras
from tensorflow.python.keras.models import load_model
import numpy as np
import os
import cv2
import random
import time

from tflite import LiteModel

keras.backend.clear_session()
model = load_model('dottrack_rotation_5deg', compile=True)

litemodel = LiteModel.from_keras_model(model)

def angular_distance(a1, a2, total=90):
    r1 = abs(a1 - a2)
    r2 = abs(total - abs(a1 - a2))
    return min(r1, r2)

def prediction_to_angle(prediction):
    vectors = []

    for i in range(len(prediction[0])):
        # extend the angles to a whole circle so angles from zero are calculated correctly
        a = ((i * 20) / 180) * np.pi
        
        length = prediction[0][i]
        vectors.append([length * np.sin(a),
                        length * np.cos(a)])
        
    # calculate vector sum (which is some kind of average) of all predictions
    vector_sum = np.sum(vectors, axis=0)
    
    # bring this vector into normal form with a magnitude of 1
    norm = np.linalg.norm(vector_sum)
    vector_sum /= norm
    
    # the angle is calculated by reversing the sine of the vector's X side
    weighted_angle = np.arcsin(vector_sum[0])
    
    # there was some mirroring/wrong orientation which I fixed with this masterpiece
    if vector_sum[0] > 0:
        weighted_angle = 2 * np.pi - weighted_angle
        if vector_sum[1] < 0:
            weighted_angle -= np.pi
        else:
            weighted_angle = 2 * np.pi - weighted_angle
    else:
        if vector_sum[1] < 0:
            weighted_angle = 2 * np.pi - weighted_angle
            weighted_angle += np.pi
            
    weighted_angle = np.rad2deg(weighted_angle)
    weighted_angle /= 4
    weighted_angle %= 90
    return weighted_angle

def calculate_angle(img):
    img = img.reshape(-1, 36,36, 1)
    img = img / 255.

    # model.predict is like a 100 times slower
    prediction = litemodel.predict(img)

    angle = prediction_to_angle(prediction)

    return(round(angle, 1))
