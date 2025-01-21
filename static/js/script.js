let currentQuestionIndex = 0;
let answeredQuestions = [];
let astigmatismIndex = 0;

// Load the first question
document.addEventListener("DOMContentLoaded", loadQuestion);

// Define astigmatism questions
const astigmatismQuestions = [
    {
        question: "散光是否规则?",
        options: [
            { text: "是", next: null, res: "规则" },
            { text: "否", next: null, res: "不规则" }
        ]
    },
    {
        question: "散光度数是否大于0.75D?",
        options: [
            { text: "是", next: null, res: "大于0.75D" },
            { text: "否", next: null, res: "小于0.75D" }
        ]
    }
];

// Eye data form event listener
document.getElementById('eyeDataForm').addEventListener('input', function() {
    const leftEyeAL = parseFloat(document.getElementById('leftEyeAL').value);
    const leftEyeCR = parseFloat(document.getElementById('leftEyeCR').value);
    const rightEyeAL = parseFloat(document.getElementById('rightEyeAL').value);
    const rightEyeCR = parseFloat(document.getElementById('rightEyeCR').value);

    const leftEyeSEOutput = document.getElementById('leftEyeSEOutput');
    const rightEyeSEOutput = document.getElementById('rightEyeSEOutput');

    if (!isNaN(leftEyeAL) && !isNaN(leftEyeCR)) {
        const leftSE = 43.86 - 14.73 * (leftEyeAL / leftEyeCR);
        leftEyeSEOutput.textContent = `左眼SE值: ${leftSE.toFixed(2)}`;
    } else {
        leftEyeSEOutput.textContent = '';
    }

    if (!isNaN(rightEyeAL) && !isNaN(rightEyeCR)) {
        const rightSE = 43.86 - 14.73 * (rightEyeAL / rightEyeCR);
        rightEyeSEOutput.textContent = `右眼SE值: ${rightSE.toFixed(2)}`;
    } else {
        rightEyeSEOutput.textContent = '';
    }
});

function loadQuestion() {
    fetch(`/get_question/${currentQuestionIndex}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
                return;
            }

            document.getElementById('currentQuestionText').innerText = data.question;
            
            const optionsContainer = document.getElementById('currentQuestionOptions');
            optionsContainer.innerHTML = '';
            data.options.forEach(option => {
                const button = document.createElement('button');
                button.innerText = option.text;
                button.onclick = () => handleAnswer(option.next, option.text, option.res, 1);
                optionsContainer.appendChild(button);
            });
        })
        .catch(error => console.error('Error:', error));
}

function handleAnswer(nextIndex, answerText, res, flag) {
    answeredQuestions.push({ 
        question: document.getElementById('currentQuestionText').innerText, 
        answer: answerText 
    });
    displayAnsweredQuestions();

    if (nextIndex === null && res !== null) {
        if (astigmatismIndex < astigmatismQuestions.length) {
            const astigmatismQuestion = astigmatismQuestions[astigmatismIndex];
            document.getElementById('currentQuestionText').innerText = astigmatismQuestion.question;
            
            const optionsContainer = document.getElementById('currentQuestionOptions');
            optionsContainer.innerHTML = '';
            astigmatismQuestion.options.forEach(option => {
                const button = document.createElement('button');
                button.innerText = option.text;
                button.onclick = () => {
                    let a = 0;
                    if(option.text === "是" && flag === 1) {
                        a = 1;
                    }
                    handleAnswer(null, option.text, res, a);
                }
                optionsContainer.appendChild(button);
            });
            astigmatismIndex++;
        } else {
            submitResults(res, flag);
        }
    } else if (nextIndex !== null) {
        currentQuestionIndex = nextIndex;
        loadQuestion();
    }
}

// function submitResults(res, flag) {
//     fetch('/submit_answer', {
//         method: 'POST',
//         headers: {
//             'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({ res, flag }),
//     })
//     .then(response => response.json())
//     .then(data => {
//         document.getElementById('resultText').innerText = data.result;
//         document.getElementById('result').style.display = 'block';
//         document.getElementById('warning-section').style.display = 'block';
//         document.getElementById('currentQuestionContainer').style.display = 'none';
//     })
//     .catch(error => console.error('Error:', error));
// }
function submitResults(res, flag) {
    // 获取患病眼信息
    const affectedEye = document.getElementById('affectedEye').value;
    
    // 根据患病眼获取对应的SE值
    let se_value;
    if (affectedEye === 'left') {
        const leftEyeAL = parseFloat(document.getElementById('leftEyeAL').value);
        const leftEyeCR = parseFloat(document.getElementById('leftEyeCR').value);
        se_value = 43.86 - 14.73 * (leftEyeAL / leftEyeCR);
    } else if (affectedEye === 'right') {
        const rightEyeAL = parseFloat(document.getElementById('rightEyeAL').value);
        const rightEyeCR = parseFloat(document.getElementById('rightEyeCR').value);
        se_value = 43.86 - 14.73 * (rightEyeAL / rightEyeCR);
    }

    fetch('/submit_answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            res, 
            flag, 
            se_value: se_value ? se_value.toFixed(2) : null,
            affected_eye: affectedEye,
            axial_length: affectedEye === 'left' ? 
                parseFloat(document.getElementById('leftEyeAL').value) : 
                parseFloat(document.getElementById('rightEyeAL').value)
        }),
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('resultText').innerText = data.result;
        // document.getElementById('result').style.display = 'block';
        document.getElementById('warning-section').style.display = 'block';
        document.getElementById('currentQuestionContainer').style.display = 'none';

        // 提取公式相关数据
        const formulaText = data.result.match(/推荐公式: (.+)/)[1];
        const linksMatch = data.result.match(/相关链接:\n([\s\S]+)/);
        const formulaLinks = linksMatch ? linksMatch[1].split("\n").map(link => link.trim()) : [];

        document.getElementById('formulaText').innerText = formulaText;
        const linksContainer = document.getElementById('formulaLinks');
        linksContainer.innerHTML = '';
        formulaLinks.forEach(link => {
            const li = document.createElement('li');
            li.innerHTML = `<a href="${link.split(': ')[1]}" target="_blank">${link.split(': ')[0]}</a>`;
            linksContainer.appendChild(li);
        });

        document.getElementById('result').style.display = 'block';

    })
    .catch(error => console.error('Error:', error));
}

function displayAnsweredQuestions() {
    const container = document.getElementById('answeredQuestions');
    container.innerHTML = '';
    answeredQuestions.forEach(item => {
        const div = document.createElement('div');
        div.className = 'answered-question';
        div.innerHTML = `<p>${item.question}: ${item.answer}</p>`;
        container.appendChild(div);
    });
}

function reload() {
    currentQuestionIndex = 0;
    astigmatismIndex = 0;
    answeredQuestions = [];
    document.getElementById('result').style.display = 'none';
    document.getElementById('warning-section').style.display = 'none';
    document.getElementById('currentQuestionContainer').style.display = 'block';
    loadQuestion();
}

function saveResults() {
    const patientName = document.getElementById('patientName').value;
    const patientAge = document.getElementById('patientAge').value;

    if (!patientName || !patientAge) {
        alert("请填写患者姓名和年龄");
        return;
    }

    fetch('/save_results', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            patientName: patientName,
            patientAge: patientAge,
            answeredQuestions: answeredQuestions,
            result: document.getElementById('resultText').innerText
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("结果已成功保存！");
        } else {
            alert("保存失败：" + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("请求失败，请稍后再试。");
    });
}