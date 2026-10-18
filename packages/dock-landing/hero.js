/* Siri-like voice orb. Three.js from a CDN. Mic only after a click. */

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const THREE_URL = "https://unpkg.com/three@0.170.0/build/three.module.js";

document.documentElement.classList.add("js");

function reveal() {
  const nodes = document.querySelectorAll(".reveal");
  if (REDUCED || !("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("is-in");
      io.unobserve(entry.target);
    }
  }, { threshold: 0.25 });
  nodes.forEach((node) => io.observe(node));
}

const NOISE = `
float hash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.11, 0.17, 0.13));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i), hash(i + vec3(1.0, 0.0, 0.0)), f.x),
        mix(hash(i + vec3(0.0, 1.0, 0.0)), hash(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
    mix(mix(hash(i + vec3(0.0, 0.0, 1.0)), hash(i + vec3(1.0, 0.0, 1.0)), f.x),
        mix(hash(i + vec3(0.0, 1.0, 1.0)), hash(i + vec3(1.0, 1.0, 1.0)), f.x), f.y),
    f.z);
}
float fbm(vec3 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.03 + vec3(1.7, 9.2, 3.4);
    a *= 0.5;
  }
  return v;
}
`;

const VERT = NOISE + `
uniform float uTime;
uniform float uAmp;
varying vec3 vNormal;
varying vec3 vObj;
varying vec3 vWorld;
void main() {
  float n = fbm(position * 1.55 + vec3(uTime * 0.18, uTime * 0.11, -uTime * 0.07));
  float n2 = fbm(position * 2.8 + vec3(-uTime * 0.22, 0.4, uTime * 0.16));
  float swell = 1.0 + uAmp * 0.2;
  float disp = (n - 0.48) * (0.16 + uAmp * 0.42) + (n2 - 0.5) * (0.05 + uAmp * 0.12);
  vec3 pos = position * swell + normal * disp;
  vec4 world = modelMatrix * vec4(pos, 1.0);
  vObj = pos;
  vWorld = world.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * world;
}
`;

const FRAG = NOISE + `
uniform float uTime;
uniform float uAmp;
varying vec3 vNormal;
varying vec3 vObj;
varying vec3 vWorld;
void main() {
  vec3 viewDir = normalize(cameraPosition - vWorld);
  float n1 = fbm(vObj * 1.35 + vec3(uTime * 0.16, -uTime * 0.08, 0.2));
  float n2 = fbm(vObj * 2.2 + vec3(-uTime * 0.12, uTime * 0.14, 0.5));
  vec3 pink = vec3(1.0, 0.34, 0.62);
  vec3 purple = vec3(0.58, 0.28, 1.0);
  vec3 blue = vec3(0.22, 0.48, 1.0);
  vec3 orange = vec3(1.0, 0.36, 0.11);
  vec3 col = mix(pink, purple, smoothstep(0.28, 0.78, n1));
  col = mix(col, blue, smoothstep(0.38, 0.86, n2));
  col = mix(col, orange, smoothstep(0.52, 0.9, n1) * smoothstep(0.2, 0.75, 1.0 - n2));
  float core = pow(clamp(1.0 - length(vObj.xy) * 0.72, 0.0, 1.0), 1.6);
  col = mix(col, vec3(1.0, 0.9, 0.97), core * (0.28 + uAmp * 0.45));
  float fres = pow(1.0 - max(dot(normalize(vNormal), viewDir), 0.0), 1.7);
  col += fres * mix(vec3(1.0, 0.62, 0.9), orange, 0.35) * (0.55 + uAmp * 0.9);
  col *= 0.85 + uAmp * 0.55;
  gl_FragColor = vec4(col, 1.0);
}
`;

const SHELL_VERT = `
varying vec3 vNormal;
varying vec3 vWorld;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * world;
}
`;

const SHELL = `
uniform float uAmp;
varying vec3 vNormal;
varying vec3 vWorld;
void main() {
  vec3 viewDir = normalize(cameraPosition - vWorld);
  float fres = pow(1.0 - max(dot(normalize(vNormal), viewDir), 0.0), 2.3);
  vec3 col = mix(vec3(0.75, 0.35, 1.0), vec3(1.0, 0.42, 0.22), fres);
  gl_FragColor = vec4(col, fres * (0.28 + uAmp * 0.55));
}
`;

let smooth = 0.18;
let analyser = null;
let buf = null;
let stream = null;
let audioCtx = null;
let listening = false;

function simulated(time) {
  const cycle = 3.4;
  const x = ((time % cycle) + cycle) % cycle;
  if (x < 1.15) return 0.05 + 0.035 * Math.sin(time * 2.1);
  const u = (x - 1.15) / (cycle - 1.15);
  const env = Math.sin(Math.PI * u);
  const wobble = 0.58 + 0.42 * Math.sin(time * 10.5) * (0.45 + 0.55 * Math.sin(time * 4.1));
  return 0.07 + env * wobble * 0.95;
}

function sample(time) {
  let target;
  if (analyser && buf) {
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i += 1) {
      const v = (buf[i] - 128) / 128;
      sum += v * v;
    }
    target = Math.min(1, Math.sqrt(sum / buf.length) * 3.6);
  } else {
    target = simulated(time);
  }
  smooth += (target - smooth) * (analyser ? 0.45 : 0.09);
  document.documentElement.style.setProperty("--amp", smooth.toFixed(3));
  return smooth;
}

function stopMic() {
  listening = false;
  analyser = null;
  buf = null;
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  const btn = document.getElementById("orb-mic");
  if (btn) {
    btn.setAttribute("aria-pressed", "false");
    btn.textContent = "Try the orb";
  }
}

function wireMic() {
  const btn = document.getElementById("orb-mic");
  if (!btn) return;
  let starting = false;
  btn.addEventListener("click", async () => {
    if (listening) {
      stopMic();
      return;
    }
    if (starting) return;
    const note = document.getElementById("orb-mic-note");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (note) note.textContent = "This browser has no mic. The orb keeps a speaking pattern.";
      return;
    }
    starting = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.72;
      source.connect(analyser);
      buf = new Uint8Array(analyser.fftSize);
      listening = true;
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "Stop the orb";
      if (note) note.textContent = "Listening. The orb follows your voice.";
    } catch (err) {
      stopMic();
      if (note) note.textContent = "Mic stayed off. The orb keeps a speaking pattern.";
    } finally {
      starting = false;
    }
  });
  window.addEventListener("pagehide", stopMic);
}

function haloTexture(THREE) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 256;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(128, 128, 8, 128, 128, 128);
  grd.addColorStop(0, "rgba(255, 170, 230, 0.55)");
  grd.addColorStop(0.28, "rgba(140, 80, 255, 0.28)");
  grd.addColorStop(0.55, "rgba(60, 120, 255, 0.14)");
  grd.addColorStop(0.78, "rgba(255, 92, 28, 0.08)");
  grd.addColorStop(1, "rgba(0, 0, 0, 0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 256, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

async function boot() {
  const canvas = document.getElementById("hero-canvas");
  if (!canvas) return false;
  let gl = null;
  try {
    gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
  } catch (err) {
    gl = null;
  }
  if (!gl) return false;

  let THREE;
  try {
    THREE = await import(THREE_URL);
  } catch (err) {
    return false;
  }

  const host = canvas.parentElement;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 30);
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas, alpha: true, antialias: true, powerPreference: "high-performance",
    });
  } catch (err) {
    return false;
  }
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  if (THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;

  const uniforms = {
    uTime: { value: 0.8 },
    uAmp: { value: 0.2 },
  };
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(1, 80, 64),
    new THREE.ShaderMaterial({
      uniforms, vertexShader: VERT, fragmentShader: FRAG, toneMapped: false,
    }),
  );
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(1.16, 48, 32),
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: SHELL_VERT,
      fragmentShader: SHELL,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      toneMapped: false,
    }),
  );
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: haloTexture(THREE),
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    opacity: 0.95,
    toneMapped: false,
  }));
  glow.scale.set(4.4, 4.4, 1);

  const ringColors = [0xff6aa8, 0x8a6bff, 0x4d8cff, 0xff5c1c];
  const rings = ringColors.map((color, i) => {
    const mesh = new THREE.Mesh(
      new THREE.RingGeometry(1.05, 1.075, 72),
      new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false,
      }),
    );
    mesh.rotation.x = i === 1 ? 1.05 : i === 3 ? -0.7 : 0.08 * i;
    mesh.rotation.y = i === 2 ? 0.55 : 0;
    return mesh;
  });

  const orb = new THREE.Group();
  orb.add(glow, shell, core, ...rings);
  scene.add(orb);

  const clock = new THREE.Clock();

  function fit() {
    const w = host.clientWidth || 1;
    const h = host.clientHeight || 1;
    camera.aspect = w / h;
    const narrow = w / h < 1;
    camera.position.set(narrow ? 0 : -0.2, narrow ? 1.15 : 0.12, narrow ? 7.1 : 6.7);
    camera.lookAt(narrow ? 0 : 1.85, narrow ? 0.95 : 0.02, 0);
    camera.updateProjectionMatrix();
    orb.position.set(narrow ? 0 : 2.05, narrow ? 1.05 : 0.02, 0);
    renderer.setSize(w, h, false);
  }

  function pose(time, amp) {
    uniforms.uTime.value = time;
    uniforms.uAmp.value = amp;
    const breathe = 1 + amp * 0.14;
    core.scale.setScalar(breathe);
    shell.scale.setScalar(1 + amp * 0.08);
    glow.scale.setScalar(4.1 + amp * 1.8);
    glow.material.opacity = 0.72 + amp * 0.28;
    rings.forEach((ring, i) => {
      const phase = ((time * (0.28 + amp * 0.45) + i * 0.23) % 1 + 1) % 1;
      const spread = 1.02 + phase * (1.05 + amp * 2.1);
      ring.scale.set(spread, spread, spread);
      ring.lookAt(camera.position);
      ring.material.opacity = (1 - phase) * (0.05 + amp * 0.7);
    });
    if (!REDUCED) orb.rotation.y = time * 0.12;
  }

  fit();
  pose(REDUCED ? 1.4 : 0.8, sample(0.8));
  renderer.render(scene, camera);
  document.documentElement.classList.add("is-webgl");

  let running = true;
  function loop() {
    if (!running) return;
    const elapsed = clock.getElapsedTime();
    pose(REDUCED ? 1.4 : elapsed, sample(elapsed));
    renderer.render(scene, camera);
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  window.addEventListener("resize", () => {
    fit();
    renderer.render(scene, camera);
  });
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) {
      clock.getDelta();
      requestAnimationFrame(loop);
    }
  });
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    running = false;
    document.documentElement.classList.remove("is-webgl");
  });
  return true;
}

let cssLoopOn = true;
function cssLoop(origin) {
  function frame(now) {
    if (!cssLoopOn) return;
    sample(REDUCED ? 1.2 : (now - origin) / 1000);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

reveal();
wireMic();
cssLoop(performance.now());
boot().then((ok) => {
  if (ok) cssLoopOn = false;
});
