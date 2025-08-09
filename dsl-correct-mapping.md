# DSL с правильным пониманием user/design space

## КЛЮЧЕВОЕ ПОНИМАНИЕ

```
User Space = то что видит пользователь (CSS font-weight: 400)
Design Space = реальные координаты в файле (может быть 125, 380, что угодно)

Regular 400 > 125 означает:
- Пользователь запрашивает: font-weight: 400 (Regular)  
- Мастер находится в точке: 125 в design space
```

---

## Правильный подход со стандартными весами

```dsl
family Kazimir

# СТАНДАРТНЫЕ user space значения (встроены в парсер):
defaults user_weights
    100 Thin
    200 ExtraLight  
    300 Light
    400 Regular
    500 Medium
    600 SemiBold
    700 Bold
    800 ExtraBold
    900 Black

# Но DESIGN SPACE у каждого шрифта свой!
axes
    weight 300:400:900  # user space диапазон
        # user > design маппинг
        300 > 0      # Light в user space 300, но мастер в точке 0!
        400 > 125    # Regular в user space 400, но мастер в точке 125!
        500 > 365    # Medium в user space 500, интерполируется в точке 365
        700 > 695    # Bold в user space 700, интерполируется в точке 695
        900 > 1000   # Black в user space 900, но мастер в точке 1000!

# Мастера в DESIGN SPACE координатах
masters
    Light       0     # design space!
    Regular     125   # design space!
    Black       1000  # design space!
```

---

## Оптимизированная запись с дефолтами

```dsl
family MyFont

# Вариант 1: Явный маппинг (когда отличается от линейного)
axes
    weight 100:400:900
        # Имена подхватываются автоматически из дефолтов
        100 > 0      # Thin (имя из дефолта) → 0 в design space
        300 > 250    # Light (имя из дефолта) → 250 в design space  
        400 > 400    # Regular → 400 (совпадает)
        700 > 800    # Bold → 800 в design space
        900 > 1000   # Black → 1000 в design space

# Вариант 2: Компактная запись для стандартных имён
axes
    weight 100:400:900
        Thin    > 0      # автоматически 100 > 0
        Light   > 250    # автоматически 300 > 250
        Regular > 400    # автоматически 400 > 400
        Bold    > 800    # автоматически 700 > 800
        Black   > 1000   # автоматически 900 > 1000

# Вариант 3: Смешанная запись
axes  
    weight 100:400:900
        # Стандартные имена - только design space
        Thin    > 0
        Light   > 250
        Regular > 400
        Bold    > 800
        Black   > 1000
        # Нестандартные - полная запись
        350 Book > 350   # Book не в дефолтах для 350
        850 Ultra > 950  # кастомное значение
```

---

## Реальный пример - Kazimir

```dsl
family Kazimir

# ПРАВИЛЬНАЯ запись с пониманием маппинга
axes
    weight 300:400:900
        Light   > 0      # user: 300, design: 0
        Regular > 125    # user: 400, design: 125  
        Medium  > 365    # user: 500, design: 365
        Bold    > 695    # user: 700, design: 695
        Black   > 1000   # user: 900, design: 1000

# Мастера указываем в DESIGN координатах
masters
    Light     [0]      # в точке 0 design space
    Regular   [125]    # в точке 125 design space
    Black     [1000]   # в точке 1000 design space

# Экземпляры генерируются по USER space именам
instances auto
    # Сгенерирует:
    # Light (user: 300, design: 0) - есть мастер ✓
    # Regular (user: 400, design: 125) - есть мастер ✓  
    # Medium (user: 500, design: 365) - интерполяция ⟵
    # Bold (user: 700, design: 695) - интерполяция ⟵
    # Black (user: 900, design: 1000) - есть мастер ✓
```

---

## Варианты записи для разных случаев

### Случай 1: Линейный маппинг (user = design)

```dsl
axes
    weight 100:400:900 linear  # linear флаг означает user = design
    # Или
    weight standard  # использует стандартный linear маппинг
```

### Случай 2: Нелинейный маппинг (типичный случай)

```dsl
axes
    weight 100:400:900
        100 > 0      # крайние точки часто в 0 и 1000
        400 > 400    # центр может совпадать
        900 > 1000
```

### Случай 3: Сложный маппинг с множеством точек

```dsl
axes
    weight 100:400:900
        # user > design  [имя берётся из дефолтов]
        100 > 0       # Thin
        200 > 140     # ExtraLight  
        300 > 240     # Light
        400 > 380     # Regular
        500 > 500     # Medium
        600 > 580     # SemiBold
        700 > 700     # Bold
        800 > 840     # ExtraBold
        900 > 1000    # Black
```

---

## Правильная реализация парсера

```python
class AxisMapping:
    def __init__(self):
        # Стандартные USER SPACE значения и имена
        self.standard_weights = {
            100: 'Thin',
            200: 'ExtraLight',
            300: 'Light',
            400: 'Regular',
            500: 'Medium',
            600: 'SemiBold',
            700: 'Bold',
            800: 'ExtraBold',
            900: 'Black'
        }
        
        # Маппинг user → design для конкретного шрифта
        self.user_to_design = {}
        self.design_to_user = {}
    
    def add_mapping(self, user_value, design_value, name=None):
        """
        user_value: значение которое видит пользователь (400)
        design_value: реальная координата в design space (125)
        name: имя стиля (Regular) - может браться из дефолтов
        """
        if name is None:
            name = self.standard_weights.get(user_value, f"Weight{user_value}")
        
        self.user_to_design[user_value] = design_value
        self.design_to_user[design_value] = user_value
        
    def parse_axis_line(self, line):
        if '>' in line:
            # Явный маппинг
            parts = line.split('>')
            left = parts[0].strip()
            design = int(parts[1].strip())
            
            # Определяем user value
            if left.isdigit():
                # "400 > 125"
                user = int(left)
                name = self.standard_weights.get(user)
            else:
                # "Regular > 125"
                name = left
                # Ищем user value для этого имени
                user = self.find_user_value_for_name(name)
            
            self.add_mapping(user, design, name)
```

---

## ИТОГ - правильный Kazimir DSSketch

```dsl
family Kazimir
suffix VAR

axes
    weight 300:400:900
        # Правильный маппинг user > design
        Light   > 0     # 300 > 0
        Regular > 125   # 400 > 125  
        Medium  > 365   # 500 > 365
        Bold    > 695   # 700 > 695
        Black   > 1000  # 900 > 1000
    
    italic binary

masters
    # Указываем design space координаты!
    Light         0    0
    Regular       125  0  @base
    Black         1000 0
    LightItalic   0    1
    Italic        125  1  @base
    BlackItalic   1000 1

rules
    cent > cent.alt @ weight >= 365  # design space координата!

# Экземпляры будут в user space для пользователя
instances auto
```
