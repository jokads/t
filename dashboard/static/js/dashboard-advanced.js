/**
 * JokaMazKiBu Trading Bot Dashboard - Advanced JavaScript v6.0
 * Efeito visual de triângulos que seguem o mouse (Canvas/WebGL).
 */

class TriangleAnimation {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.mouse = { x: this.width / 2, y: this.height / 2 };
        this.points = [];
        this.numPoints = 50;
        this.maxDist = 150;
        this.triangleColor = 'rgba(255, 215, 0, 0.05)'; // Dourado transparente
        this.init();
    }

    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        window.addEventListener('mousemove', (e) => this.updateMouse(e));
        
        this.initPoints();
        this.loop();
    }

    resizeCanvas() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
    }

    updateMouse(e) {
        this.mouse.x = e.clientX;
        this.mouse.y = e.clientY;
    }
    
    initPoints() {
        this.points = [];
        for (let i = 0; i < this.numPoints; i++) {
            this.points.push(this.createPoint(Math.random() * this.width, Math.random() * this.height));
        }
    }
    
    createPoint(x, y) {
        return {
            x: x,
            y: y,
            vx: Math.random() * 0.5 - 0.25,
            vy: Math.random() * 0.5 - 0.25,
            radius: 1
        };
    }

    updatePoint(p) {
        p.x += p.vx;
        p.y += p.vy;

        // Limites do canvas
        if (p.x < 0 || p.x > this.width) p.vx *= -1;
        if (p.y < 0 || p.y > this.height) p.vy *= -1;
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Adiciona o ponto do mouse
        const allPoints = [...this.points, this.mouse];

        for (let i = 0; i < allPoints.length; i++) {
            const p1 = allPoints[i];
            if (p1 !== this.mouse) this.updatePoint(p1);

            for (let j = i + 1; j < allPoints.length; j++) {
                const p2 = allPoints[j];
                const dist = Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2));

                if (dist < this.maxDist) {
                    // Desenha a linha
                    const alpha = 1 - (dist / this.maxDist);
                    this.ctx.strokeStyle = this.triangleColor.replace('0.05', alpha * 0.5);
                    this.ctx.lineWidth = 0.5;
                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.stroke();

                    // Desenha triângulos (apenas para o ponto do mouse e seus vizinhos mais próximos)
                    if (i === allPoints.length - 1) { // Se p1 é o ponto do mouse
                        for (let k = j + 1; k < allPoints.length; k++) {
                            const p3 = allPoints[k];
                            const dist2 = Math.sqrt(Math.pow(p2.x - p3.x, 2) + Math.pow(p2.y - p3.y, 2));
                            const dist3 = Math.sqrt(Math.pow(p1.x - p3.x, 2) + Math.pow(p1.y - p3.y, 2));

                            if (dist2 < this.maxDist && dist3 < this.maxDist) {
                                // Desenha o triângulo
                                const avgDist = (dist + dist2 + dist3) / 3;
                                const triAlpha = 1 - (avgDist / this.maxDist);
                                this.ctx.fillStyle = this.triangleColor.replace('0.05', triAlpha * 0.1);
                                this.ctx.beginPath();
                                this.ctx.moveTo(p1.x, p1.y);
                                this.ctx.lineTo(p2.x, p2.y);
                                this.ctx.lineTo(p3.x, p3.y);
                                this.ctx.closePath();
                                this.ctx.fill();
                            }
                        }
                    }
                }
            }
        }
    }

    loop() {
        this.draw();
        requestAnimationFrame(() => this.loop());
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Inicializa a animação de triângulos
    new TriangleAnimation('triangle-canvas');
});
