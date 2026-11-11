from pathlib import Path
from xml.etree import ElementTree as ET

from spec import BENCHMARK_DIR, BODY_COUNTS, BODY_MASS, BODY_SIZE, SCENARIOS, TIME_STEP, body_positions


def node(parent, tag, value=None, **attributes):
    element = ET.SubElement(parent, tag, attributes)
    if value is not None:
        element.text = str(value)
    return element


def make_world(count, scenario):
    sdf = ET.Element('sdf', version='1.10')
    world = node(sdf, 'world', name='selection')
    physics = node(world, 'physics', name='fixed_step', type='ignored')
    node(physics, 'max_step_size', TIME_STEP)
    node(physics, 'real_time_factor', 0)
    node(world, 'gravity', '0 0 -9.81')
    node(world, 'plugin', filename='gz-sim-physics-system', name='gz::sim::systems::Physics')
    ground = node(world, 'model', name='ground')
    node(ground, 'static', 'true')
    ground_link = node(ground, 'link', name='ground_link')
    ground_collision = node(ground_link, 'collision', name='ground_collision')
    ground_geometry = node(ground_collision, 'geometry')
    ground_plane = node(ground_geometry, 'plane')
    node(ground_plane, 'normal', '0 0 1')
    node(ground_plane, 'size', '10 10')
    for index, position in enumerate(body_positions(count, scenario)):
        model = node(world, 'model', name=f'box_{index}')
        node(model, 'pose', ' '.join(map(str, position)) + ' 0 0 0')
        link = node(model, 'link', name='body')
        inertial = node(link, 'inertial')
        node(inertial, 'mass', BODY_MASS)
        inertia = node(inertial, 'inertia')
        length, width, height = BODY_SIZE
        for key, number in (
            ('ixx', BODY_MASS * (width ** 2 + height ** 2) / 12),
            ('iyy', BODY_MASS * (length ** 2 + height ** 2) / 12),
            ('izz', BODY_MASS * (length ** 2 + width ** 2) / 12),
            ('ixy', 0), ('ixz', 0), ('iyz', 0)
        ):
            node(inertia, key, number)
        collision = node(link, 'collision', name='collision')
        geometry = node(collision, 'geometry')
        shape = node(geometry, 'box')
        node(shape, 'size', ' '.join(map(str, BODY_SIZE)))
        surface = node(collision, 'surface')
        friction = node(surface, 'friction')
        ode = node(friction, 'ode')
        node(ode, 'mu', 0.8)
        node(ode, 'mu2', 0.8)
    ET.indent(sdf, space='  ')
    return ET.tostring(sdf, encoding='unicode')


def main():
    output = BENCHMARK_DIR / 'worlds'
    output.mkdir(exist_ok=True)
    for scenario in SCENARIOS:
        for count in BODY_COUNTS:
            (output / f'{scenario}_{count}.sdf').write_text(make_world(count, scenario))
    print('Generated 6 Gazebo scenes from benchmark/spec.py')


if __name__ == '__main__':
    main()
