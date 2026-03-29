// document.addEventListener('DOMContentLoaded', function() {
//     const uploadForm = document.getElementById('uploadForm');
//     const submitBtn = document.getElementById('submitBtn');
//     const progress = document.getElementById('progress');
//     const result = document.getElementById('result');
//     const error = document.getElementById('error');

//     if (uploadForm) {
//         uploadForm.addEventListener('submit', async function(e) {
//             e.preventDefault();

//             // Сброс состояния
//             result.style.display = 'none';
//             error.style.display = 'none';
            
//             // Показываем прогресс
//             progress.style.display = 'block';
//             submitBtn.disabled = true;
            
//             const formData = new FormData(uploadForm);

//             try {
//                 const response = await fetch('/upload', {
//                     method: 'POST',
//                     body: formData
//                 });

//                 const data = await response.json();

//                 if (!response.ok) {
//                     throw new Error(data.error || 'Ошибка при обработке');
//                 }

//                 // Показываем результаты
//                 displayResults(data.result);
                
//             } catch (err) {
//                 error.textContent = err.message;
//                 error.style.display = 'block';
//             } finally {
//                 progress.style.display = 'none';
//                 submitBtn.disabled = false;
//             }
//         });
//     }

//     function displayResults(resultData) {
//         const resultContent = document.getElementById('resultContent');
        
//         // Статистика
//         let statsHtml = '<div class="stats">';
//         for (const [key, value] of Object.entries(resultData.stats || {})) {
//             statsHtml += `
//                 <div class="stat-item">
//                     <span class="stat-label">${key}</span>
//                     <span class="stat-value">${value}</span>
//                 </div>
//             `;
//         }
//         statsHtml += '</div>';
        
//         // Файлы
//         let filesHtml = '<h3>Сгенерированные файлы:</h3><div class="files-list">';
//         for (const file of resultData.files || []) {
//             filesHtml += `
//                 <div class="file-item">
//                     <div class="file-info">
//                         <span class="file-name">${file.name}</span>
//                         <span class="file-size">${file.size}</span>
//                     </div>
//                     <a href="${file.url}" class="btn btn-small" download>Скачать</a>
//                 </div>
//             `;
//         }
//         filesHtml += '</div>';
        
//         // Кнопка скачать все
//         filesHtml += `
//             <div style="text-align: center; margin-top: 20px;">
//                 <a href="${resultData.download_url}" class="btn btn-primary">
//                     📥 Скачать все файлы (ZIP)
//                 </a>
//             </div>
//         `;
        
//         resultContent.innerHTML = statsHtml + filesHtml;
//         result.style.display = 'block';
        
//         // Прокрутка к результатам
//         result.scrollIntoView({ behavior: 'smooth' });
//     }

//     // Предпросмотр выбранных файлов
//     const fileInputs = document.querySelectorAll('input[type="file"]');
//     fileInputs.forEach(input => {
//         input.addEventListener('change', function() {
//             const wrapper = this.closest('.file-input-wrapper');
//             const infoDiv = wrapper.querySelector('.file-info');
            
//             if (this.files.length > 0) {
//                 const file = this.files[0];
//                 const size = (file.size / 1024).toFixed(1);
//                 infoDiv.textContent = `Выбран: ${file.name} (${size} KB)`;
//                 infoDiv.style.color = '#27ae60';
//             } else {
//                 const originalText = this.id === 'run_file' ? 'Выберите файл РУН ППС (обязательно)' :
//                                     this.id === 'schedule_file' ? 'Выберите файл расписания (обязательно)' :
//                                     'Опционально, если нужны дополнительные настройки';
//                 infoDiv.textContent = originalText;
//                 infoDiv.style.color = '';
//             }
//         });
//     });

//     // Сброс формы
//     const resetBtn = document.querySelector('button[type="reset"]');
//     if (resetBtn) {
//         resetBtn.addEventListener('click', function() {
//             fileInputs.forEach(input => {
//                 const wrapper = input.closest('.file-input-wrapper');
//                 const infoDiv = wrapper.querySelector('.file-info');
//                 const originalText = input.id === 'run_file' ? 'Выберите файл РУН ППС (обязательно)' :
//                                     input.id === 'schedule_file' ? 'Выберите файл расписания (обязательно)' :
//                                     'Опционально, если нужны дополнительные настройки';
//                 infoDiv.textContent = originalText;
//                 infoDiv.style.color = '';
//             });
            
//             result.style.display = 'none';
//             error.style.display = 'none';
//         });
//     }
// });

document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const submitBtn = document.getElementById('submitBtn');
    const progress = document.getElementById('progress');
    const result = document.getElementById('result');
    const error = document.getElementById('error');

    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Сброс состояния
            result.style.display = 'none';
            error.style.display = 'none';
            
            // Показываем прогресс
            progress.style.display = 'block';
            submitBtn.disabled = true;
            
            const formData = new FormData(uploadForm);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Ошибка при обработке');
                }

                // Показываем результаты
                displayResult(data.result);
                
            } catch (err) {
                error.textContent = err.message;
                error.style.display = 'block';
            } finally {
                progress.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
    }

    function displayResult(resultData) {
        const resultContent = document.getElementById('resultContent');
        
        const file = resultData.file;
        
        resultContent.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 3em; margin-bottom: 20px;">📊</div>
                <h3 style="margin-bottom: 15px;">Расписание готово!</h3>
                <p style="margin-bottom: 20px; color: #666;">Размер файла: ${file.size}</p>
                <a href="${file.url}" class="btn btn-primary" style="font-size: 1.2em; padding: 15px 40px;" download>
                    📥 Скачать расписание
                </a>
                <p style="margin-top: 20px;">
                    <a href="/upload" style="color: var(--primary-color);">🔄 Сгенерировать другое расписание</a>
                </p>
            </div>
        `;
        
        result.style.display = 'block';
        result.scrollIntoView({ behavior: 'smooth' });
    }

    // Предпросмотр выбранных файлов
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const wrapper = this.closest('.file-input-wrapper');
            const infoDiv = wrapper.querySelector('.file-info');
            
            if (this.files.length > 0) {
                const file = this.files[0];
                const size = (file.size / 1024).toFixed(1);
                infoDiv.textContent = `Выбран: ${file.name} (${size} KB)`;
                infoDiv.style.color = '#27ae60';
            } else {
                const originalText = this.id === 'run_file' ? 'Выберите файл РУН ППС (обязательно)' :
                                    this.id === 'schedule_file' ? 'Выберите файл расписания (обязательно)' : '';
                infoDiv.textContent = originalText;
                infoDiv.style.color = '';
            }
        });
    });

    // Сброс формы
    const resetBtn = document.querySelector('button[type="reset"]');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            fileInputs.forEach(input => {
                const wrapper = input.closest('.file-input-wrapper');
                const infoDiv = wrapper.querySelector('.file-info');
                const originalText = input.id === 'run_file' ? 'Выберите файл РУН ППС (обязательно)' :
                                    input.id === 'schedule_file' ? 'Выберите файл расписания (обязательно)' : '';
                infoDiv.textContent = originalText;
                infoDiv.style.color = '';
            });
            
            result.style.display = 'none';
            error.style.display = 'none';
        });
    }
});