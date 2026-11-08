// Bundled once with esbuild into three-bundle.js (classic script, works from file://, no ES-module CORS issue).
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
window.THREE = Object.assign({}, THREE, { RoundedBoxGeometry, RoomEnvironment, GLTFLoader, RGBELoader });
