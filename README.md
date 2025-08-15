# DesignSpace Sketch

**Человеко-ориентированная альтернатива DesignSpace XML**

DSSketch предоставляет простой, интуитивно понятный текстовый формат для описания вариативных шрифтов, заменяя перегруженный и сложный XML-формат на чистый, читаемый текст, который дизайнеры шрифтов могут легко понимать и редактировать вручную. Это делает разработку вариативных шрифтов более доступной и менее подверженной ошибкам.

Компактный формат с двунаправленным преобразованием сокращает многословные .designspace файлы в 10-20 раз при сохранении полной функциональности.

## Основные возможности

- **Компактность**: DSSketch сокращает многословные .designspace файлы в 10-20 раз
- **Читаемость**: понятная структура с человеческими именами
- **Правильный маппинг**: корректное разделение User Space (CSS) и Design Space (интерполяция)
- **Автоматизация**: автогенерация повторяющихся элементов
- **Стандарты**: встроенные значения для стандартных весов и ширин

## Использование

### Командная строка

```bash
# DesignSpace → DSSketch (с автоматической валидацией UFO)
python dssketch_cli.py font.designspace

# DSSketch → DesignSpace
python dssketch_cli.py font.dssketch

# С явным указанием выходного файла
python dssketch_cli.py input.designspace -o output.dssketch

# Обратная совместимость (старый способ)
python dssketch.py font.designspace
```

### Python API

DSSketch предоставляет удобный Python API для интеграции в другие проекты:

```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# Загрузить DesignSpace объект и конвертировать в DSSketch файл
ds = DesignSpaceDocument()
ds.read("MyFont.designspace")
dssketch.convert_to_dss(ds, "MyFont.dssketch")

# Конвертировать DSSketch файл в DesignSpace объект
ds = dssketch.convert_to_designspace("MyFont.dssketch")

# Работа с DSSketch строками (для программной генерации)
dss_content = """
family MyFont
axes
    wght 100:400:900
        Light > 100
        Regular > 400 @elidable
        Bold > 900
masters [wght]
    Light.ufo [100]
    Regular.ufo [400] @base
    Bold.ufo [900]
"""

# Конвертировать DSSketch строку в DesignSpace объект
ds = dssketch.convert_dss_string_to_designspace(dss_content, base_path="./")

# Конвертировать DesignSpace объект в DSSketch строку
dss_string = dssketch.convert_designspace_to_dss_string(ds)
```

**Преимущества API:**
- Простая интеграция в существующие рабочие процессы
- Работа с объектами DesignSpace напрямую
- Программная генерация DSSketch контента
- Обработка ошибок и валидация
- 84-97% сокращение размера при конвертации

## Пример DSSketch формата

```dssketch
family SuperFont

axes
    wght 50:400:900
        Hairline > 0
        Thin > 68
        Light > 196
        Regular > 362 @elidable
        Medium > 477
        Bold > 732
        Black > 1000

    ital discrete
        Upright @elidable
        Italic

masters [wght, ital]
    Hairline        [0, 0]
    Regular         [362, 0] @base
    Black           [1000, 0]
    HairlineItalic  [0, 1]
    Italic          [362, 1] @base
    BlackItalic     [1000, 1]

rules
    dollar cent > .rvrn @ weight >= 480
    * > .alt @ weight >= 600

instances auto
```

## Ключевые концепции

### User Space vs Design Space

```
User Space = значения которые видит пользователь (font-weight: 400)
Design Space = координаты где находятся мастера для интерполяции

Пример маппинга:
Regular > 362  означает:
- Пользователь запрашивает font-weight: 400 (Regular)
- Мастер находится в точке 362 в design space
```

### Стандартные веса (встроенные)

Конвертер автоматически распознает стандартные веса:

- 100: Thin
- 200: ExtraLight
- 300: Light
- 400: Regular
- 500: Medium
- 600: SemiBold
- 700: Bold
- 800: ExtraBold
- 900: Black

## Примеры файлов

В папке `examples/` находятся:

- `SuperFont-Variable.designspace` → сложный пример с нелинейным маппингом
- `Nagel_VF.designspace` → пример с наклоном (slant)
- `SuperFont-compact.dss` → компактный DSS формат

## Архитектура

### Основные компоненты

- `DSSParser` - парсер DSS в структурированные данные
- `DSSWriter` - генератор DSS из структурированных данных
- `DesignSpaceToDSS` - конвертер .designspace → DSS
- `DSSToDesignSpace` - конвертер DSS → .designspace
- `Standards` - встроенные маппинги весов и ширин
- `instances` - модуль для управления инстансами шрифтов

### API функции высокого уровня

- `convert_to_dss()` - конвертация DesignSpace объекта в DSSketch файл
- `convert_to_designspace()` - конвертация DSSketch файла в DesignSpace объект
- `convert_dss_string_to_designspace()` - конвертация DSSketch строки в DesignSpace объект
- `convert_designspace_to_dss_string()` - конвертация DesignSpace объекта в DSSketch строку

### Модуль instances.py

Новый модуль `instances.py` предоставляет полный набор функций для работы с инстансами вариативных шрифтов:

**Основные функции:**
- `createInstances()` - создание всех возможных инстансов из комбинаций осей
- `sortAxisOrder()` - **уважает порядок осей из DSS документа** или использует стандартный порядок
- `getElidabledNames()` - генерация вариаций стилевых названий с удаляемыми частями
- `getInstancesMapping()` - извлечение маппинга значений осей
- `createInstance()` - создание одного дескриптора инстанса
- `copyDS()` - копирование DesignSpace документа с выбором компонентов
- `removeInstances()` - удаление инстансов по фильтру

**Особенности:**
- **Контролируемый порядок осей**: инстансы генерируются в порядке, заданном в секции `axes`
- **Гибкая последовательность**: измените порядок осей в DSS для управления названиями инстансов
- **Обратная совместимость**: fallback к стандартному порядку при отсутствии DSS контекста

**Константы:**
- `ELIDABLE_MAJOR_AXIS = "weight"` - основная ось, которая не должна удаляться
- `DEFAULT_AXIS_ORDER` - fallback порядок осей: Optical, Contrast, Width, Weight, Italic, Slant
- `DEFAULT_INSTANCE_FOLDER = "instances"` - папка по умолчанию для файлов инстансов

## Возможности DSSketch

### Компактные формы записи

```dssketch
# Вместо длинного XML можно писать:
weight wght 100:400:900
    Thin > 0
    Regular > 400
    Black > 1000

# Или еще компактнее:
weight standard  # использует линейный маппинг 100-900
```

### Автоматизация

```dssketch
instances auto          # генерирует все разумные комбинации
masters scan *.ufo      # автопоиск мастеров по паттерну

# Контроль порядка генерации инстансов через последовательность осей
axes
    ital discrete       # Первая ось - italic будет первым в названиях
        Upright
        Italic
    wght 100:400:900    # Вторая ось - weight будет вторым
        Light > 100
        Regular > 400
# Результат: "Italic Light", "Upright Bold" и т.д.
```

### Правила подстановки

```dssketch
rules
    # Переключение для тяжелых весов
    dollar > dollar.heavy @ weight >= 480
    cent > cent.heavy @ weight >= 480

    # Составные условия
    ampersand > ampersand.fancy @ weight >= 600 && width >= 110

    # Точные значения и диапазоны
    a > a.special @ weight == 500
    b > b.narrow @ 80 <= width <= 120
```

## Сравнение размеров

| Формат | Строки | Размер | Читаемость |
|--------|--------|---------|------------|
| .designspace | 266 | 11.2 KB | ⭐⭐ |
| .dssketch | 21 | 0.8 KB | ⭐⭐⭐⭐⭐ |

**Экономия: 93% размера, 10x читаемость**
# Test change for git hook
