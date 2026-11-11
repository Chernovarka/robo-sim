import argparse
import json
import math
from pathlib import Path
from statistics import median

from spec import BODY_COUNTS, ENGINES, SCENARIOS, get_profile


def valid_run(record):
    return (record.get('valid') is True and isinstance(record.get('measurements'), dict)
            and all(key in record['measurements'] for key in ('steps_per_second', 'memory_peak_bytes', 'core_cpu_s')))


def evaluate(records):
    trials = {}
    for record in records:
        key = (record['scenario'], record['count'], record['repetition'], record['engine'])
        if key in trials:
            raise ValueError(f'Duplicate result: {key}')
        trials[key] = record
    repetitions = {record['repetition'] for record in records}
    if not repetitions:
        raise ValueError('No results')
    expected = {(scenario, count, repetition, engine)
                for scenario in SCENARIOS for count in BODY_COUNTS
                for repetition in repetitions for engine in ENGINES}
    complete = set(trials) == expected
    workload_medians = {}
    engine_ok = {}
    for engine in ENGINES:
        engine_records = [record for record in records if record['engine'] == engine]
        engine_ok[engine] = (complete and len(engine_records) == len(SCENARIOS) * len(BODY_COUNTS) * len(repetitions)
                             and all(valid_run(record) for record in engine_records))
        for scenario in SCENARIOS:
            for count in BODY_COUNTS:
                subset = [record for record in engine_records
                          if record['scenario'] == scenario and record['count'] == count and valid_run(record)]
                if subset:
                    workload_medians[(engine, scenario, count)] = {
                        'steps_per_second': median(record['measurements']['steps_per_second'] for record in subset),
                        'memory_mib': median(record['measurements']['memory_peak_bytes'] / 1048576 for record in subset),
                        'core_cpu_s': median(record['measurements']['core_cpu_s'] for record in subset
                                             if record['measurements']['core_cpu_s'] is not None)
                        if any(record['measurements']['core_cpu_s'] is not None for record in subset) else None,
                    }
    scores = {}
    if complete and all(engine_ok.values()) and len(repetitions) >= 10:
        for engine in ENGINES:
            ratios = []
            for scenario in SCENARIOS:
                for count in BODY_COUNTS:
                    current = workload_medians[(engine, scenario, count)]['steps_per_second']
                    best = max(workload_medians[(candidate, scenario, count)]['steps_per_second']
                               for candidate in ENGINES)
                    ratios.append(current / best)
            scores[engine] = math.exp(sum(math.log(ratio) for ratio in ratios) / len(ratios))
    ranking = sorted(scores, key=scores.get, reverse=True)
    return {
        'complete': complete, 'repeats': len(repetitions), 'engine_ok': engine_ok,
        'metrics': workload_medians, 'scores': scores, 'ranking': ranking,
        'total': len(records), 'expected': len(expected),
    }


def render(summary, profile, input_path):
    lines = [
        '# RoboSim: отчёт об отборочном бенчмарке',
        '',
        f'Исходные измерения: `{input_path}`.',
        '',
        '## Протокол',
        '',
        'Одни и те же 6 физических сцен: 1, 8 и 32 тела на полу либо падают на пол.',
        'Геометрия каждого тела: 0,30 × 0,24 × 0,12 м; масса: 2 кг.',
        f'Физический шаг: {profile["physics_dt_seconds"]} с; '
        f'прогрев: {profile["warmup_steps"]} шагов; '
        f'измеряемая часть: {profile["measured_steps"]} шагов.',
        f'Лимиты: {profile["cpus"]} CPU, cpuset={profile["cpuset_cpus"]}, '
        f'{profile["memory_bytes"] / 1048576:.0f} MiB RAM, swap=0, без GUI и сети.',
        'Запуски последовательные; порядок движков чередуется между повторами.',
        '',
        '## Полнота данных',
        '',
        f'Получено {summary["total"]} из {summary["expected"]} обязательных запусков; '
        f'повторов на нагрузку: {summary["repeats"]}.',
        '',
        '| Движок | Все запуски корректны |',
        '|---|---|',
    ]
    for engine in ENGINES:
        lines.append(f'| {engine} | {"Да" if summary["engine_ok"][engine] else "Нет"} |')
    lines += ['', '## Результаты', '',
              '| Сцена | Тел | Движок | Медиана шагов/с | Пиковая RAM, MiB | CPU-время, с |',
              '|---|---:|---|---:|---:|---:|']
    for scenario in SCENARIOS:
        for count in BODY_COUNTS:
            for engine in ENGINES:
                metrics = summary['metrics'].get((engine, scenario, count))
                if metrics:
                    cpu = f'{metrics["core_cpu_s"]:.3f}' if metrics['core_cpu_s'] is not None else '—'
                    lines.append(f'| {scenario} | {count} | {engine} | '
                                 f'{metrics["steps_per_second"]:.1f} | '
                                 f'{metrics["memory_mib"]:.1f} | {cpu} |')
                else:
                    lines.append(f'| {scenario} | {count} | {engine} | — | — | — |')
    lines += ['', '## Правило отбора', '',
              'Для каждого из шести сценариев вычисляется медианная скорость в шагах/с.',
              'Скорость нормируется на лучшую медиану среди движков в том же сценарии.',
              'Итоговая оценка — геометрическое среднее шести нормированных скоростей.',
              'Не прошедший хотя бы один контроль корректности, лимит ресурсов или таймаут '
              'движок не получает итоговой оценки.',
              'Пиковая RAM и CPU-время обязательно публикуются; при разнице оценок не более 10% '
              'второй критерий — меньшая медианная RAM по шести сценариям.',
              'Если доля неполных или некорректных запусков ненулевая, итоговый выбор '
              'по скоростному рейтингу не выполняется.',
              '']
    if summary['ranking']:
        ranking = summary['ranking'][:]
        memory = {engine: median(summary['metrics'][(engine, scenario, count)]['memory_mib']
                                 for scenario in SCENARIOS for count in BODY_COUNTS)
                  for engine in ENGINES}
        for left_index in range(len(ranking)):
            for right_index in range(left_index + 1, len(ranking)):
                left, right = ranking[left_index], ranking[right_index]
                if abs(summary['scores'][left] - summary['scores'][right]) / max(summary['scores'][left], summary['scores'][right]) <= 0.10:
                    if memory[right] < memory[left]:
                        ranking[left_index], ranking[right_index] = ranking[right_index], ranking[left_index]
        lines += ['| Движок | Нормированная скорость | Медианная RAM, MiB |',
                  '|---|---:|---:|']
        for engine in ranking:
            lines.append(f'| {engine} | {summary["scores"][engine]:.4f} | {memory[engine]:.1f} |')
        lines += ['', f'**Два лидера по установленному правилу: {ranking[0]} и {ranking[1]}.**',
                  '', 'Это решение относится к данной ограниченной батарее физических микронагрузок, '
                  'а не к точности моделирования датчиков или полноценной робототехнической системе.']
    else:
        lines += ['**Окончательный отбор не выполнен.** Пилот, данные неполные либо есть неудачные запуски.',
                  'Если это пилот — выполнить основную серию. Иначе проверить ошибки в JSONL и повторить измерение после исправления инфраструктуры.']
    lines += ['', '## Ограничения', '',
              'Движки используют разные решатели контактов и разные физические движки по умолчанию. '
              'Равные параметры сцены не гарантируют равную численную погрешность.',
              'Время и потребление памяти относятся к образам, версиям и аппаратной конфигурации запуска.',
              'Полные стендовые испытания реальных роботов, датчиков и интеграции с Яндекс.Контест '
              'остаются отдельным этапом после предварительного отбора.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('docs/SELECTION_RESULTS.md'))
    args = parser.parse_args()
    records = [json.loads(line) for line in args.source.read_text().splitlines() if line.strip()]
    summary = evaluate(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(summary, get_profile(), args.source), encoding='utf-8')
    print('Wrote:', args.output)
    if not summary['ranking']:
        if summary['repeats'] >= 10:
            raise SystemExit(1)
        print('Pilot only: no final selection')
    else:
        print('Leaders:', ', '.join(summary['ranking'][:2]))


if __name__ == '__main__':
    main()
