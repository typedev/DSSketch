# DesignSpace Sketch

**Человеко-ориентированная альтернатива DesignSpace XML**

DSSketch предоставляет простой, интуитивно понятный текстовый формат для описания переменных шрифтов, заменяя перегруженный и сложный XML-формат на чистый, читаемый текст, который дизайнеры шрифтов могут легко понимать и редактировать вручную. Это делает разработку переменных шрифтов более доступной и менее подверженной ошибкам.

Компактный формат с двунаправленным преобразованием сокращает многословные .designspace файлы в 10-20 раз при сохранении полной функциональности.

## Основные возможности

- **Компактность**: DSSketch сокращает многословные .designspace файлы в 10-20 раз
- **Читаемость**: понятная структура с человеческими именами
- **Правильный маппинг**: корректное разделение User Space (CSS) и Design Space (интерполяция)
- **Автоматизация**: автогенерация повторяющихся элементов
- **Стандарты**: встроенные значения для стандартных весов и ширин

## Использование

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

## Пример DSSketch формата

```dssketch
family KazimirText

axes
    wght 50:400:900
        Hairline > 0
        Thin > 68
        Light > 196
        Regular > 362  
        Medium > 477
        Bold > 732
        Black > 1000
    
    ital binary

masters
    Hairline        [0, 0]
    Regular         [362, 0] @base
    Black           [1000, 0]
    HairlineItalic  [0, 1]
    Italic          [362, 1] @base
    BlackItalic     [1000, 1]

rules
    dollar > dollar.rvrn @ weight >= 480
    cent > cent.rvrn @ weight >= 480

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

- `KazimirText-Variable.designspace` → сложный пример с нелинейным маппингом
- `Nagel_VF.designspace` → пример с наклоном (slant)
- `kazimir-compact.dss` → компактный DSS формат

## Архитектура

- `DSSParser` - парсер DSS в структурированные данные
- `DSSWriter` - генератор DSS из структурированных данных  
- `DesignSpaceToDSS` - конвертер .designspace → DSS
- `DSSToDesignSpace` - конвертер DSS → .designspace
- `Standards` - встроенные маппинги весов и ширин

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
