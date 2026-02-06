# Структуры данных Arc Browser и Zen Browser

Документация основана на анализе скриптов миграции arc2zen.

**Последнее обновление**: Февраль 2026

---

## Arc Browser

### Расположение данных (macOS)

```
~/Library/Application Support/Arc/StorableSidebar.json
```

Файл в формате **обычного JSON** (не сжат).

### Структура StorableSidebar.json

```json
{
  "sidebar": {
    "containers": [
      {
        "spaces": [...],      // Пространства (Spaces) — могут быть dict или string
        "items": [...],       // Закладки и папки
        "global": true/false  // Признак основного профиля (Main Profile)
      },
      // ... другие контейнеры (профили)
    ]
  }
}
```

**Важно**: `containers` может содержать пустые элементы или элементы без `spaces`/`items` — их нужно пропускать.

### Space (Пространство)

```json
{
  "id": "uuid",
  "title": "Space Name",           // Название (может отсутствовать → "Space N")
  "newContainerIDs": [
    {"pinned": true},              // Маркер pinned контейнера
    "container-uuid-1",            // ID контейнера для pinned вкладок
    {"unpinned": true},            // Маркер unpinned контейнера  
    "container-uuid-2"             // ID контейнера для unpinned вкладок
  ]
}
```

**Особенности**:
- `newContainerIDs` — связанный список пар `{marker}, container_id`
- Marker: `{"pinned": true}` или иное (без "pinned" = unpinned)
- В массиве `spaces` могут быть **string** entries (ID или references) — их нужно пропускать
- Spaces без `newContainerIDs` — пропускать

### Item (Закладка или Папка)

```json
{
  "id": "uuid",
  "parentID": "parent-uuid",       // ID родительского элемента (container_id для top-level)
  "childrenIds": ["id1", "id2"],   // Упорядоченный список дочерних ID
  
  // Для закладки (tab):
  "title": "Custom Title",         // Опционально — пользовательское название
  "data": {
    "tab": {
      "savedURL": "https://...",
      "savedTitle": "Page Title"   // Оригинальный title страницы
    }
  },
  
  // Для папки:
  "title": "Folder Name"
  // (нет поля "data")
}
```

**Определение типа**:
- Если есть `data.tab` → это **закладка**
- Если есть `title` без `data.tab` → это **папка**

**Получение title закладки** (приоритет):
1. `item.title` (пользовательское название)
2. `item.data.tab.savedTitle` (оригинальный title)
3. `"Untitled"` (fallback)

### Иерархия

```
Container (Profile)
  └── Space
        ├── Pinned Container ID
        │     └── Item (folder or bookmark)
        │           └── childrenIds → дочерние Items
        └── Unpinned Container ID (опционально, если include_unpinned=True)
              └── Item...
```

### Множественные профили

Если в `containers` несколько контейнеров с данными:
- Контейнер с `"global": true` → "Main Profile"
- Остальные → "Profile N"

---

## Zen Browser

### Расположение данных (macOS)

```
~/Library/Application Support/zen/Profiles/<profile>/
├── zen-sessions.jsonlz4           # Основной файл сессии
└── sessionstore-backups/
    ├── recovery.jsonlz4           # Backup сессии
    └── recovery.baklz4            # Дублирующий backup
```

### Формат файлов

**mozLz4** — LZ4 сжатие с заголовком `mozLz40\0` (8 байт).

```python
# Чтение
with open(path, "rb") as f:
    data = f.read()
assert data[:8] == b"mozLz40\0"
json_data = lz4.block.decompress(data[8:])

# Запись
compressed = lz4.block.compress(json.dumps(data).encode())
with open(path, "wb") as f:
    f.write(b"mozLz40\0")
    f.write(compressed)
```

### Структура zen-sessions.jsonlz4

```json
{
  "spaces": [...],           // Workspaces
  "tabs": [...],             // Все вкладки
  "folders": [...],          // Папки
  "groups": [...],           // Группы (связаны с папками 1:1)
  "lastCollected": 1234567   // Timestamp (ms)
}
```

### Структура recovery.jsonlz4

```json
{
  "windows": [
    {
      "tabs": [...],
      "folders": [...],
      "groups": [...]
    }
  ],
  "session": {
    "lastUpdate": 1234567    // Timestamp (ms)
  }
}
```

### Workspace (Пространство)

```json
{
  "uuid": "workspace-uuid",
  "name": "Workspace Name"
}
```

### Tab (Вкладка)

```json
{
  "entries": [
    {
      "url": "https://...",
      "title": "Page Title",
      "cacheKey": 0,
      "ID": 123456789,
      "docshellUUID": "{uuid}",
      "resultPrincipalURI": null,
      "hasUserInteraction": false,
      "triggeringPrincipal_base64": "{\"3\":{}}",
      "docIdentifier": 123,
      "transient": false,
      "navigationKey": "{uuid}",
      "navigationId": "{uuid}"
    }
  ],
  "lastAccessed": 1234567890,          // Timestamp (ms)
  "pinned": true,                       // Закреплённая вкладка
  "hidden": false,
  
  // Zen-специфичные поля:
  "zenWorkspace": "workspace-uuid",     // Привязка к workspace
  "zenSyncId": "1234567890-42",         // Уникальный ID (timestamp-random)
  "zenEssential": false,
  "zenDefaultUserContextId": null,
  "zenPinnedIcon": null,
  "zenIsEmpty": false,                  // True для placeholder вкладок папок
  "zenHasStaticIcon": false,
  "zenGlanceId": null,
  "zenIsGlance": false,
  
  // Для вкладок в папке:
  "groupId": "folder-id",               // ID папки/группы
  
  // Дополнительно для pinned вкладок:
  "_zenPinnedInitialState": {
    "entry": {
      "url": "https://...",
      "title": "Page Title",
      ...
    },
    "image": null
  },
  
  "searchMode": null,
  "userContextId": 0,
  "attributes": {},
  "index": 1,
  "userTypedValue": "",
  "userTypedClear": 0,
  "image": null
}
```

### Folder (Папка)

```json
{
  "id": "folder-id",                    // Совпадает с group.id
  "name": "Folder Name",
  "workspaceId": "workspace-uuid",      // Привязка к workspace
  "parentId": "parent-folder-id",       // Для вложенных папок (null для root)
  "prevSiblingInfo": {                  // Порядок среди sibling
    "type": "folder",                   // "folder" или "start"
    "id": "prev-folder-id"              // null если первый
  },
  "emptyTabIds": ["sync-id-1", ...],    // ID placeholder вкладок
  "pinned": true,
  "splitViewGroup": false,
  "collapsed": true,
  "saveOnWindowClose": true,
  "userIcon": ""
}
```

**Важно**: `emptyTabIds` должен содержать `zenSyncId` всех empty tab'ов этой папки И всех дочерних папок (propagate вверх по иерархии).

### Group (Группа)

```json
{
  "id": "folder-id",                    // Совпадает с folder.id
  "name": "Folder Name",
  "color": "zen-workspace-color",
  "pinned": true,
  "splitView": false,
  "collapsed": true,
  "saveOnWindowClose": true
}
```

**Связь**: Folder и Group всегда имеют одинаковый `id`. Group определяет визуальные свойства, Folder — структуру.

### Empty Tab (Placeholder)

Каждая папка в Zen **обязательно** требует placeholder вкладку:

```json
{
  "entries": [{"url": "about:blank", "title": ""}],
  "pinned": true,
  "hidden": false,
  "groupId": "folder-id",              // Привязка к папке
  "zenWorkspace": "workspace-uuid",
  "zenSyncId": "1234567890-42",        // Этот ID добавляется в folder.emptyTabIds
  "zenIsEmpty": true,                  // Ключевой флаг!
  // ... остальные zen-поля
}
```

### Генерация ID

```python
def generate_id() -> str:
    """Формат: timestamp_ms-random(0-99)"""
    ts = int(datetime.now().timestamp() * 1000)
    rand = random.randint(0, 99)
    return f"{ts}-{rand}"
```

Пример: `"1738857600000-42"`

---

## Связи в Zen (визуально)

```
Workspace (uuid: "ws-123")
│
├── Folder (id: "f-1", workspaceId: "ws-123", parentId: null)
│   │   prevSiblingInfo: {type: "start", id: null}
│   │   emptyTabIds: ["sync-1", "sync-2"]  ← собирает все empty tabs
│   │
│   ├── Empty Tab (zenSyncId: "sync-1", groupId: "f-1", zenIsEmpty: true)
│   │
│   ├── Tab (groupId: "f-1", zenWorkspace: "ws-123")
│   │
│   └── Nested Folder (id: "f-2", parentId: "f-1")
│           prevSiblingInfo: {type: "start", id: null}
│           emptyTabIds: ["sync-2"]
│           │
│           └── Empty Tab (zenSyncId: "sync-2", groupId: "f-2")
│
├── Folder (id: "f-3", workspaceId: "ws-123", parentId: null)
│       prevSiblingInfo: {type: "folder", id: "f-1"}  ← после f-1
│
└── Standalone Tab (zenWorkspace: "ws-123", no groupId)

Group "f-1" ←→ Folder "f-1"  (1:1 связь по id)
Group "f-2" ←→ Folder "f-2"
Group "f-3" ←→ Folder "f-3"
```

---

## Маппинг Arc → Zen

| Arc | Zen |
|-----|-----|
| Container | Profile |
| Space | Workspace |
| Folder (item с title) | Folder + Group + Empty Tab |
| Tab (item с data.tab) | Tab с pinned=true |
| Space.pinned container | zenWorkspace |
| item.parentID | folder.parentId + tab.groupId |
| item.childrenIds | prevSiblingInfo linked list |

### Особенности миграции

1. **Empty Tab**: Каждая папка в Zen требует placeholder вкладку с `zenIsEmpty: true`

2. **Propagation emptyTabIds**: ID empty tab'ов должны распространяться вверх по иерархии папок

3. **Sibling Order**: В Zen порядок папок определяется linked list через `prevSiblingInfo`, а не массивом

4. **Двойная запись**: Данные записываются в `zen-sessions.jsonlz4` И в `recovery.jsonlz4` (+ `recovery.baklz4`)

---

## Полезные пути (macOS)

```bash
# Arc Browser
~/Library/Application Support/Arc/StorableSidebar.json

# Zen Browser
~/Library/Application Support/zen/Profiles/
~/Library/Application Support/zen/Profiles/*/zen-sessions.jsonlz4
~/Library/Application Support/zen/Profiles/*/sessionstore-backups/recovery.jsonlz4
```

---

## Профили Zen Browser

Профили находятся в `~/Library/Application Support/zen/Profiles/`.

Формат имени: `<random>.default` или `<random>.default-release`.

**Поиск профиля** (приоритет):
1. Папка с "default" в имени
2. Любая первая папка

---

## Бекапы (arc2zen)

При миграции создаются бекапы:

```
<profile>/zen-sessions.jsonlz4.backup_YYYYMMDD_HHMMSS
<profile>/sessionstore-backups/recovery.jsonlz4.backup_YYYYMMDD_HHMMSS
```

**Формат timestamp**: `YYYYMMDD_HHMMSS` (например `20260206_143052`)

---

## Известные ограничения

### Arc Browser
- Unpinned вкладки по умолчанию не мигрируются (флаг `include_unpinned`)
- Некоторые spaces могут быть без названия → генерируется "Space N"

### Zen Browser  
- **Zen должен быть закрыт** перед записью в файлы сессии
- Данные нужно писать в **оба файла**: `zen-sessions.jsonlz4` и `recovery.jsonlz4`
- `recovery.baklz4` — копия `recovery.jsonlz4`, тоже обновляется
- Каждая папка **обязательно** требует empty tab placeholder
- Empty tab IDs должны **propagate вверх** по иерархии папок

### Миграция
- Workspace в Zen должен существовать до импорта (создаётся вручную)
- Matching по имени: сначала exact match, потом case-insensitive

---

## Зависимости Python

```
lz4  # Для работы с mozLz4 файлами Zen
```

---

## Ссылки

- [Zen Browser](https://zen-browser.app/) — основан на Firefox
- [Arc Browser](https://arc.net/) — Chromium-based
- Формат mozLz4 — стандартный для Firefox/Zen session files
