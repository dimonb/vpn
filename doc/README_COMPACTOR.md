# Network Compactor - Документация

## Описание

`NetworkCompactor` - это интеллектуальный алгоритм компактификации списков IPv4/IPv6 сетей, интегрированный в cfgapp.

### Ключевые особенности

✅ **100% покрытие** - гарантирует, что все исходные сети покрыты результатом
✅ **Адаптивный алгоритм** - автоматически подбирает оптимальный баланс
✅ **Контроль размера** - ограничивает максимальный размер результирующих сетей
✅ **IPv4 и IPv6** - поддержка обеих версий протокола

## Использование

### В production (через переменные окружения)

NetworkCompactor интегрирован в cfgapp и **включен по умолчанию**.

Настройки по умолчанию в `.env`:

```bash
# Компактификация включена по умолчанию
ENABLE_COMPACTION=true

# Целевое количество сетей после компактификации
COMPACT_TARGET_MAX=200

# Минимальный префикс для IPv4 (11 = max /11 = 2M IPs)
COMPACT_MIN_PREFIX_V4=11

# Минимальный префикс для IPv6
COMPACT_MIN_PREFIX_V6=32
```

Чтобы **отключить** компактификацию:
```bash
ENABLE_COMPACTION=false
```

При старте приложения вы увидите в логах:
```
INFO - Network Compaction: ENABLED (target: 200, IPv4 min prefix: /11, IPv6 min prefix: /32)
```

При обработке NETSET файлов:
```
NETSET expanded 199 entries (IPv4→/18, IPv6→/32) [compacted to ~200]
```

### Через IPProcessor (программный способ)

NetworkCompactor также доступен напрямую в коде:

```python
from src.utils import IPProcessor

# Создаём процессор с включенной компактификацией
processor = IPProcessor(
    ipv4_block_prefix=18,
    ipv6_block_prefix=32,
    enable_compaction=True,       # Включить компактификацию
    compact_target_max=200,        # Целевое количество сетей
    compact_min_prefix_v4=11,      # Минимальный префикс IPv4 (/11 = 2M IPs)
    compact_min_prefix_v6=32,      # Минимальный префикс IPv6
)

# Читаем NETSET файл
with open('networks.netset') as f:
    netset_text = f.read()

# Обрабатываем и компактифицируем
result = processor.netset_expand(netset_text, ",PROXY,no-resolve")

# result теперь содержит компактифицированные IP-CIDR правила
for line in result:
    print(line)
# IP-CIDR,192.168.0.0/22,PROXY,no-resolve
# IP-CIDR,10.0.0.0/16,PROXY,no-resolve
```

### Напрямую через NetworkCompactor

```python
from src.utils import NetworkCompactor, compact_ipv4_networks

# Простой вариант через convenience функцию
cidrs = ["192.168.0.0/24", "192.168.1.0/24", "192.168.2.0/24"]
result = compact_ipv4_networks(cidrs, target_max=50, min_prefix=20)
print(result)  # ['192.168.0.0/22']

# Через класс NetworkCompactor
nets = NetworkCompactor.compact_networks(
    cidrs,
    target_max=200,  # Целевое количество сетей
    min_prefix=11,   # Минимальный префикс (max /11 = 2M IP)
    version=4        # IPv4
)

# Проверка покрытия
is_covered, not_covered = NetworkCompactor.verify_coverage(cidrs, nets)
if is_covered:
    print("✅ Все сети покрыты!")
```

## Параметры

### `target_max` - целевое количество сетей

Алгоритм будет стремиться к этому количеству. Реальный результат может немного отличаться.

- Меньше значение = больше увеличение покрытия
- Больше значение = меньше увеличение покрытия

**Рекомендации:**
- Для AWS (1600+ сетей): `target_max=200` → ~200 сетей, 3x увеличение
- Для Google (100 сетей): `target_max=50` → ~46 сетей, 2.26x увеличение

### `min_prefix` - минимальный префикс (максимальный размер сети)

Для IPv4:
- `8` = /8 (16,777,216 IP) - очень агрессивно
- `9` = /9 (8,388,608 IP)
- `10` = /10 (4,194,304 IP)
- `11` = /11 (2,097,152 IP) - **рекомендуется** ✅
- `12` = /12 (1,048,576 IP) - консервативно
- `13` = /13 (524,288 IP)

Для IPv6:
- `16` = /16 - очень большие блоки
- `32` = /32 - **рекомендуется** ✅
- `48` = /48 - консервативно

## Результаты на реальных данных

### AWS IP ranges (1633 сети)

```python
result = compact_ipv4_networks(cidrs, target_max=200, min_prefix=11)
```

**Результат:**
- Исходно: 1633 сети, 95 млн IP
- Результат: 199 сетей, 287 млн IP
- Сокращение: 87.8%
- Увеличение покрытия: 3.00x
- Покрытие: ✅ 100%

### Google IP ranges (97 сетей)

```python
result = compact_ipv4_networks(cidrs, target_max=50, min_prefix=11)
```

**Результат:**
- Исходно: 97 сетей, 22 млн IP
- Результат: 46 сетей, 50 млн IP
- Сокращение: 52.6%
- Увеличение покрытия: 2.26x
- Покрытие: ✅ 100%

## Тестирование

```bash
# Запуск всех тестов
pytest tests/test_compactor.py -v

# Запуск с покрытием
pytest tests/test_compactor.py --cov=src.utils --cov-report=html

# Только интеграционные тесты
pytest tests/test_compactor.py -k "real_data"
```

## Интеграция с cfgapp

NetworkCompactor полностью интегрирован в `IPProcessor`. Компактификация включается через параметр `enable_compaction=True`.

### Пример использования в Template Processor

```python
from src.utils import IPProcessor

# Создать процессор с компактификацией для больших списков
processor = IPProcessor(
    ipv4_block_prefix=18,
    enable_compaction=True,
    compact_target_max=200,
    compact_min_prefix_v4=11
)

# При обработке NETSET файлов
netset_content = load_netset_file("aws-ips.netset")
rules = processor.netset_expand(netset_content, ",PROXY,no-resolve")

# rules теперь содержит компактифицированный список
# Вместо 1633 правил получим ~200 с гарантией полного покрытия
```

### Когда включать компактификацию

**Рекомендуется включать** когда:
- Список содержит >500 сетей
- Требуется уменьшить размер конфигурации
- Производительность роутинга важнее точности диапазонов

**Не рекомендуется** когда:
- Список уже содержит <100 сетей
- Критична точность диапазонов (например, биллинг)
- Нельзя допустить случайное попадание "чужих" IP

### Параметры по умолчанию

```python
IPProcessor(
    enable_compaction=False,      # По умолчанию выключено
    compact_target_max=200,        # Целевое количество
    compact_min_prefix_v4=11,      # IPv4: max /11 (2M IPs)
    compact_min_prefix_v6=32,      # IPv6: max /32
)
```

## Алгоритм

1. **Базовое схлопывание** - удаление перекрывающихся сетей
2. **Адаптивное объединение** - постепенное увеличение порога стоимости:
   - Сортировка сетей по адресам
   - Поиск соседних пар для объединения
   - Объединение если стоимость (доп. IP) ≤ порог
   - Пороги: 1M → 2M → 4M → 8M → 16M адресов
3. **Проверка покрытия** - гарантия 100% покрытия исходных сетей

## Тестовые данные

Находятся в `tests/fixtures/`:
- `ipv4_merged.txt` - AWS IP ranges (1633 сети)
- `ipv4_merged2.txt` - Google IP ranges (97 сетей)

## API Reference

### NetworkCompactor.compact_networks()

```python
@staticmethod
def compact_networks(
    cidrs: list[str],
    target_max: int = 200,
    min_prefix: int = 11,
    version: int = 4,
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]
```

**Параметры:**
- `cidrs` - список CIDR строк
- `target_max` - целевое максимальное количество
- `min_prefix` - минимальная длина префикса
- `version` - версия IP (4 или 6)

**Возвращает:** список объектов Network

### NetworkCompactor.verify_coverage()

```python
@staticmethod
def verify_coverage(
    original_cidrs: list[str],
    compacted_nets: list[Network],
) -> tuple[bool, list[str]]
```

**Возвращает:** `(is_fully_covered, list_of_not_covered)`

### Convenience функции

```python
compact_ipv4_networks(cidrs, target_max=200, min_prefix=11) -> list[str]
compact_ipv6_networks(cidrs, target_max=200, min_prefix=32) -> list[str]
```

Возвращают список строк CIDR вместо объектов Network.
