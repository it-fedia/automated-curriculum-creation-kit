from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import sys
import os
import shutil
from datetime import datetime
import traceback
import logging
from logging.handlers import RotatingFileHandler
import secrets

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Добавляем путь к основному приложению
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Импортируем pipeline
try:
    from core.pipeline import build_timetable_bundle
    logger.info(" Модуль pipeline успешно импортирован")
except Exception as e:
    logger.error(f" Ошибка импорта pipeline: {e}")
    logger.error(traceback.format_exc())
    build_timetable_bundle = None

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Конфигурация
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['UPLOAD_FOLDER'] = BASE_DIR / 'uploads'
app.config['RESULTS_FOLDER'] = BASE_DIR / 'results'
app.config['ALLOWED_EXTENSIONS'] = {'.xlsx', '.xls'}
app.config['MAX_FILE_AGE'] = 24  # часов

# Создаем папки
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['RESULTS_FOLDER'].mkdir(exist_ok=True)

# Логирование в файл
log_file = BASE_DIR / 'app.log'
file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=10)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('=== Запуск приложения ===')

def allowed_file(filename):
    return Path(filename).suffix.lower() in app.config['ALLOWED_EXTENSIONS']

def clean_old_files(folder, hours=None):
    if hours is None:
        hours = app.config['MAX_FILE_AGE']
    
    now = datetime.now().timestamp()
    cleaned = 0
    for item in Path(folder).glob('*'):
        if item.is_file() and now - item.stat().st_mtime > hours * 3600:
            item.unlink()
            cleaned += 1
        elif item.is_dir() and now - item.stat().st_mtime > hours * 3600:
            shutil.rmtree(item)
            cleaned += 1
    
    if cleaned > 0:
        app.logger.info(f"Очищено {cleaned} старых файлов из {folder}")
    return cleaned

def get_file_size_str(file_path):
    size = file_path.stat().st_size
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'pipeline_available': build_timetable_bundle is not None
    })

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        try:
            app.logger.info("Получен POST запрос на /upload")
            
            if build_timetable_bundle is None:
                return jsonify({'error': 'Модуль обработки не загружен'}), 500
            
            # Проверка файлов
            if 'run_file' not in request.files:
                return jsonify({'error': 'Не загружен файл РУН ППС'}), 400
            if 'schedule_file' not in request.files:
                return jsonify({'error': 'Не загружен файл расписания'}), 400
            
            run_file = request.files['run_file']
            schedule_file = request.files['schedule_file']
            
            if run_file.filename == '':
                return jsonify({'error': 'Не выбран файл РУН ППС'}), 400
            if schedule_file.filename == '':
                return jsonify({'error': 'Не выбран файл расписания'}), 400
            
            if not allowed_file(run_file.filename):
                return jsonify({'error': 'Файл РУН ППС должен быть Excel (.xlsx, .xls)'}), 400
            if not allowed_file(schedule_file.filename):
                return jsonify({'error': 'Файл расписания должен быть Excel (.xlsx, .xls)'}), 400
            
            # Очистка старых файлов
            clean_old_files(app.config['UPLOAD_FOLDER'])
            clean_old_files(app.config['RESULTS_FOLDER'])
            
            # Сохранение файлов
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            session_id = secrets.token_hex(8)
            file_prefix = f"{timestamp}_{session_id}"
            
            run_path = app.config['UPLOAD_FOLDER'] / f'run_{file_prefix}_{secure_filename(run_file.filename)}'
            schedule_path = app.config['UPLOAD_FOLDER'] / f'schedule_{file_prefix}_{secure_filename(schedule_file.filename)}'
            
            run_file.save(str(run_path))
            schedule_file.save(str(schedule_path))
            
            app.logger.info(f"Сохранены файлы: {run_path.name}, {schedule_path.name}")
            
            # Папка для результатов
            out_dir = app.config['RESULTS_FOLDER'] / f"{timestamp}_{session_id}"
            out_dir.mkdir(exist_ok=True)
            
            # ВРЕМЕННЫЙ файл mappings (пустой Excel)
            temp_mappings = app.config['UPLOAD_FOLDER'] / f"temp_mappings_{file_prefix}.xlsx"
            
            # Создаем пустой Excel файл для mappings
            import pandas as pd
            empty_df = pd.DataFrame()
            empty_df.to_excel(temp_mappings, index=False)
            
            app.logger.info(f"Запуск обработки...")
            
            try:
                # Передаем Path объекты как требует pipeline
                result = build_timetable_bundle(
                    Path(run_path),
                    Path(schedule_path),
                    Path(out_dir),
                    Path(temp_mappings)
                )
                app.logger.info("Обработка успешно завершена")
            except Exception as e:
                app.logger.error(f"Ошибка при обработке: {str(e)}")
                app.logger.error(traceback.format_exc())
                return jsonify({'error': f'Ошибка при обработке: {str(e)}'}), 500
            finally:
                # Удаляем временный файл mappings
                if temp_mappings.exists():
                    temp_mappings.unlink()
            
            # Ищем только timetable_by_teachers.xlsx
            timetable_file = None
            for file_path in out_dir.glob('timetable_by_teachers.xlsx'):
                if file_path.is_file():
                    timetable_file = {
                        'name': 'timetable_by_teachers.xlsx',
                        'display_name': '📊 Расписание по преподавателям',
                        'size': get_file_size_str(file_path),
                        'url': url_for('download_file', folder=out_dir.name, filename=file_path.name)
                    }
                    break
            
            if not timetable_file:
                return jsonify({'error': 'Файл с расписанием не найден'}), 500
            
            # Формируем ответ только с одним файлом
            response_data = {
                'success': True,
                'result': {
                    'timestamp': timestamp,
                    'session_id': session_id,
                    'file': timetable_file
                }
            }
            
            return jsonify(response_data)
            
        except Exception as e:
            app.logger.error(f"Необработанная ошибка: {str(e)}")
            app.logger.error(traceback.format_exc())
            return jsonify({'error': f'Внутренняя ошибка: {str(e)}'}), 500
    
    return render_template('upload.html')

@app.route('/download/<folder>/<filename>')
def download_file(folder, filename):
    if '..' in folder or '..' in filename:
        return "Некорректный запрос", 400
    
    file_path = app.config['RESULTS_FOLDER'] / folder / filename
    if not file_path.exists():
        return "Файл не найден", 404
    
    return send_file(
        str(file_path), 
        as_attachment=True, 
        download_name='расписание_по_преподавателям.xlsx'
    )

@app.route('/api/status')
def api_status():
    upload_files = list(Path(app.config['UPLOAD_FOLDER']).glob('*'))
    result_folders = list(Path(app.config['RESULTS_FOLDER']).glob('*'))
    
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'pipeline_available': build_timetable_bundle is not None
    })

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'Файл слишком большой. Максимальный размер: 50MB'}), 413

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error="Страница не найдена"), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"Внутренняя ошибка: {str(e)}")
    return render_template('error.html', error="Внутренняя ошибка сервера"), 500

if __name__ == '__main__':
    clean_old_files(app.config['UPLOAD_FOLDER'])
    clean_old_files(app.config['RESULTS_FOLDER'])
    app.run(debug=True, host='0.0.0.0', port=5000)