from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math
import numpy as np
from img2pos import SCREEN_W_PX, SCREEN_H_PX, IMAGE_MODE, GEOMETRY_MODE

TEXT_COLOR_RED = (50, 0, 200, 255)
TEXT_COLOR_BLUE = (200, 0, 50, 255)

# size of displayed M5Stacks in pixels
m5_w = 60
m5_h = 60

# import things
font = ImageFont.truetype('FreeMonoBold.ttf', 40)
font_battery = ImageFont.truetype('FreeMonoBold.ttf', 16)

img_m5 = Image.open("m5stack.png").convert('RGBA')
img_m5_ghost = Image.open("m5stack_ghost.png").convert('RGBA')

img_m5 = img_m5.resize((m5_w, m5_h))
img_m5_ghost = img_m5_ghost.resize((m5_w, m5_h))

def get_distance(x1, x2, y1, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def get_center(x1, x2, y1, y2):
    xdist = abs(x1 - x2) / 2
    ydist = abs(y1 - y2) / 2
    return (min(x1, x2) + xdist, min(y1, y2) + ydist)

def get_angle(x1, x2, y1, y2):
    dx = x2 - x1
    dy = y2 - y1
    angle = math.atan2(dy, dx)
    deg = np.rad2deg(angle)
    return deg

def get_angle_between(a1, a2):
    a1 = np.deg2rad(a1)
    a2 = np.deg2rad(a2)
    angle = math.atan2(math.sin(a1 - a2), math.cos(a1 - a2))
    deg = np.rad2deg(angle)
    return deg

def draw_grid(draw):
    num_lines_x = 8
    for i in range(num_lines_x):
        line_x = int(SCREEN_W_PX / num_lines_x) * i
        draw.line([line_x, 0, line_x, SCREEN_H_PX], fill=128)
    draw.line([0, int(SCREEN_H_PX * 0.33), SCREEN_W_PX, int(SCREEN_H_PX * 0.33)], fill=128)
    draw.line([0, int(SCREEN_H_PX * 0.66), SCREEN_W_PX, int(SCREEN_H_PX * 0.66)], fill=128)

def draw_geometry_distance(draw, drawText, m5stacks):
    text_color = TEXT_COLOR_RED
    (x1, y1) = m5stacks[0].getPosition()
    (x2, y2) = m5stacks[1].getPosition()
    distance = int(get_distance(x1, x2, y1, y2)) / 10.0
    text_position = get_center(x1, x2, y1, y2)
    # measure distance
    if x2 != 0:
        draw.line([x1, y1, x2, y2], fill=128, width=5)
        drawText.text((text_position[0] + 10, text_position[1] + 10), "{} cm".format(distance), font=font, fill=text_color)

def draw_geometry_pythagoras(draw, drawText, m5stacks):
    text_color = TEXT_COLOR_RED
    (x1, y1) = m5stacks[0].getPosition()
    (x2, y2) = m5stacks[1].getPosition()
    (x3, y3) = m5stacks[2].getPosition()
    if x3 != 0 and x2 != 0:
        arc_size = 50
        a1 = int(get_angle(x1, x2, y1, y2))
        a2 = int(get_angle(x1, x3, y1, y3))

        b2 = int(get_angle(x2, x1, y2, y1))
        b1 = int(get_angle(x2, x3, y2, y3))

        c2 = int(get_angle(x3, x1, y3, y1))
        c1 = int(get_angle(x3, x2, y3, y2))

        theta1 = abs(a2 - a1)
        theta2 = abs(b2 - b1)
        theta3 = abs(c2 - c1)

        draw.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=(255, 255, 255))

        text_position = get_center(x1, x2, y1, y2)
        distance = int(get_distance(x1, x2, y1, y2)) / 10.0
        drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

        text_position = get_center(x2, x3, y2, y3)
        distance = int(get_distance(x2, x3, y2, y3)) / 10.0
        drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

        text_position = get_center(x1, x3, y1, y3)
        distance = int(get_distance(x1, x3, y1, y3)) / 10.0
        drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

        if(abs(min(a1, a2) - min(a1, a2) + theta1) < 180):
            draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], min(a1, a2), min(a1, a2) + theta1, fill=128, width=5)
        else:
            draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], max(a1, a2), min(a1, a2), fill=128, width=5)
            theta1 = 360 - abs(max(a1, a2) - min(a1, a2))

        if(abs(min(b1, b2) - min(b1, b2) + theta2) < 180):
            draw.arc([x2 - arc_size, y2 - arc_size, x2 + arc_size, y2 + arc_size], min(b1, b2), min(b1, b2) + theta2, fill=128, width=5)
        else:
            draw.arc([x2 - arc_size, y2 - arc_size, x2 + arc_size, y2 + arc_size], max(b1, b2), min(b1, b2), fill=128, width=5)
            theta2 = 360 - abs(max(b1, b2) - min(b1, b2))

        if(abs(min(c1, c2) - min(c1, c2) + theta3) < 180):
            draw.arc([x3 - arc_size, y3 - arc_size, x3 + arc_size, y3 + arc_size], min(c1, c2), min(c1, c2) + theta3, fill=128, width=5)
        else:
            draw.arc([x3 - arc_size, y3 - arc_size, x3 + arc_size, y3 + arc_size], max(c1, c2), min(c1, c2), fill=128, width=5)
            theta3 = 360 - abs(max(c1, c2) - min(c1, c2))

        drawText.text((x1 + 10, y1 + 30), "{}°".format(theta1), font=font, fill=text_color)
        drawText.text((x2 + 10, y2 + 30), "{}°".format(theta2), font=font, fill=text_color)
        drawText.text((x3 + 10, y3 + 30), "{}°".format(theta3), font=font, fill=text_color)

        draw.line([x1, y1, x2, y2], fill=128, width=5)
        draw.line([x2, y2, x3, y3], fill=128, width=5)
        draw.line([x1, y1, x3, y3], fill=128, width=5)


def draw_m5stacks(preview, text, draw, drawText, m5stacks, show_relative=True):
    for m5 in m5stacks:
        (x, y) = m5.getPosition() # in pixels
        x = round(x, 2)
        y = round(y, 2)

        (abs_x, abs_y) = m5.absolute_coords # in pixels

        img_m5_temp = img_m5.copy()

        # draw raw image on the virtual M5Stack's Display
        try:
            pattern = Image.fromarray(m5.raw_img).convert('RGBA')
            img_m5_temp.paste(pattern, (12, 8), pattern)
        except:
            print("could not load image")
            pass

        # adjust rotation
        img_m5_temp = img_m5_temp.rotate(360 - m5.last_angle)

        # draw text with coordinates
        text_color = TEXT_COLOR_RED
        if(m5.hasMoved() and not IMAGE_MODE and show_relative):
            text_color = TEXT_COLOR_BLUE
            preview.paste(img_m5_ghost, (int(abs_x - (m5_w / 2)), int(abs_y - (m5_h / 2))), img_m5)
        drawText.text((10, (m5.number+1) * 50), "{}, {}".format(x, y), font=font, fill=text_color)
        preview.paste(img_m5_temp, (int(x - (m5_w / 2)), int(y - (m5_h / 2))), img_m5)
        drawText.text((x - 20, y + 35), '{}'.format(m5.power), font=font_battery, fill=TEXT_COLOR_RED)

    preview.paste(text, (0, 0), text)

def show_cupboard_demo(draw, m5):
    for i in range(3):
        if( m5.getPosition()[0] > i * (SCREEN_W_PX / 3) and
            m5.getPosition()[0] < (i + 1) * (SCREEN_W_PX / 3)):
            color = (255, 0, 0)
        else:
            color = (50, 50, 50)

        left = int(SCREEN_W_PX * 0.1)
        right = int(SCREEN_W_PX * 0.9)
        top = int(SCREEN_H_PX * 0.1) + i * (SCREEN_H_PX / 4)
        bottom = top + (SCREEN_H_PX / 4)

        draw.rectangle([left, 
                        top,
                        right,
                        bottom],
                        fill=color,
                        outline=(0, 0, 0),
                        width=5)

def show_sensor_image(preview, draw, m5):
    SENSOR_IMAGE_WIDTH = 1000
    SENSOR_IMAGE_HEIGHT = 1000
    pattern = Image.fromarray(m5.raw_img).convert('RGBA')
    pattern = pattern.resize((SENSOR_IMAGE_WIDTH, SENSOR_IMAGE_HEIGHT), Image.NEAREST)
    preview.paste(pattern, (int(SCREEN_W_PX / 2 - SENSOR_IMAGE_WIDTH / 2), int(SCREEN_H_PX / 2 - SENSOR_IMAGE_HEIGHT / 2)), pattern)
