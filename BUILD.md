# Сборка Windows x64

Нужны Python 3.12 x64 и Inno Setup 6 с русским языковым файлом.
Для обработчика Проводника нужны MSVC x64 Build Tools и Windows 10/11 SDK.
`build.ps1` сначала собирает COM DLL через `build_shell_helper.ps1` со статическим
CRT и явными INCLUDE/LIB/PATH, затем сбрасывает PATH для PyInstaller. Готовая DLL
лежит рядом с EXE под версионным именем, её импорты и экспорты проверяет verify_build.py.
Из корня проекта:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
.\Build_Tools\build.ps1 -WorkRoot C:\BuildWork\AudioPlayer
```

Готовая папка — `AudioPlayer/`. Скрипт использует минимальный PATH, проверяет
происхождение DLL и выбирает согласованный MSVC runtime из PySide6.
При наличии старой готовой папки сначала сохраните её настройки и переместите
или удалите именно эту папку вручную. Кеши и work-каталоги не очищаются.

Обязательная неинтерактивная проверка, без показа окна:

```powershell
.\AudioPlayer\AudioPlayer.exe --smoke-test C:\BuildWork\AudioPlayer\smoke.json
```

Проверьте код завершения, stderr/stdout и `ok: true` в отчёте. Проверка создаёт
временный WAV, проверяет импорт Qt/PyAV/NumPy/Mutagen, ресурсы и реальный PCM.
Промежуточный `COLLECT-00.toc` и `binary-origins.json` сохраняются для аудита.
Интеграционный тест COM использует AUDIOPLAYER_SHELL_HELPER с путём к собранной
DLL либо готовую DLL текущей версии в AudioPlayer/. Регистрация тестовая,
выделение больше100 файлов и длины командной строки не затрагивает UserChoice.

Установщик компилируется из `Build_Tools/AudioPlayer.iss` через ISCC с параметрами
`/DPayloadDir=<абсолютная готовая папка>` и `/DInstallerOutput=<папка вывода>`.
Он выбирает `D:\Apps\AudioPlayer`, если есть диск D, иначе `C:\Apps\AudioPlayer`.
Существующий `settings.json` не входит в установщик и не заменяется при обновлении.

Проверки исходников: установите pytest и Ruff в `.venv`, запустите
`python -m pytest` и `python -m ruff check .` проектным интерпретатором.
MP3/APE fixtures задаются переменными `AUDIOPLAYER_MP3_FIXTURE` и
`AUDIOPLAYER_APE_FIXTURE`; для генерации остальных тестовых файлов нужен FFmpeg.
