import { useEffect, useRef, useState } from "react";
import { niftiUrl } from "../api/client";
import * as nifti from "nifti-reader-js";

interface Props {
  path: string;
}

const COLORMAPS: Record<string, (v: number, min: number, max: number) => [number, number, number, number]> = {
  gray: (v, min, max) => {
    const t = max > min ? (v - min) / (max - min) : 0;
    const g = Math.round(t * 255);
    return [g, g, g, 255];
  },
  turbo: (v, min, max) => {
    const t = max > min ? (v - min) / (max - min) : 0;
    const r = Math.round(Math.min(255, Math.max(0, 255 * (1.5 - Math.abs(4 * t - 3)))));
    const g = Math.round(Math.min(255, Math.max(0, 255 * (1.5 - Math.abs(4 * t - 2)))));
    const b = Math.round(Math.min(255, Math.max(0, 255 * (1.5 - Math.abs(4 * t - 1)))));
    return [r, g, b, 255];
  },
};

const DTYPE_FLOAT32 = 16;
const DTYPE_INT16 = 4;
const DTYPE_UINT8 = 2;

export function NiftiViewer({ path }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [slice, setSlice] = useState(0);
  const [orient, setOrient] = useState<"axial" | "coronal" | "sagittal">("axial");
  const [colormap, setColormap] = useState("turbo");
  const [dims, setDims] = useState<[number, number, number]>([0, 0, 0]);
  const dataRef = useRef<{ volume: Float32Array; dims: [number, number, number] } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch(niftiUrl(path));
      const rawBuf = await res.arrayBuffer();
      let buf: ArrayBuffer;
      if (nifti.isCompressed(rawBuf)) {
        buf = nifti.decompress(rawBuf) as ArrayBuffer;
      } else {
        buf = rawBuf;
      }
      const header = nifti.readHeader(buf);
      if (!header) return;
      const image = nifti.readImage(header, buf);
      if (cancelled) return;

      const dims: [number, number, number] = [header.dims[1], header.dims[2], header.dims[3]];
      let volume: Float32Array;

      if (header.datatypeCode === DTYPE_FLOAT32) {
        volume = new Float32Array(image);
      } else if (header.datatypeCode === DTYPE_INT16) {
        const raw = new Int16Array(image);
        volume = new Float32Array(raw.length);
        for (let i = 0; i < raw.length; i++) volume[i] = raw[i];
      } else if (header.datatypeCode === DTYPE_UINT8) {
        const raw = new Uint8Array(image);
        volume = new Float32Array(raw.length);
        for (let i = 0; i < raw.length; i++) volume[i] = raw[i];
      } else {
        volume = new Float32Array(image);
      }

      dataRef.current = { volume, dims };
      setDims(dims);
      setSlice(Math.floor(dims[2] / 2));
    })();
    return () => { cancelled = true; };
  }, [path]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !dataRef.current) return;
    const { volume, dims } = dataRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let imgW: number, imgH: number;
    let data: Float32Array;
    const [nx, ny, nz] = dims;

    if (orient === "axial") {
      imgW = nx; imgH = ny;
      data = new Float32Array(nx * ny);
      for (let y = 0; y < ny; y++)
        for (let x = 0; x < nx; x++)
          data[y * nx + x] = volume[(slice * ny + y) * nx + x];
    } else if (orient === "coronal") {
      imgW = nx; imgH = nz;
      data = new Float32Array(nx * nz);
      for (let z = 0; z < nz; z++)
        for (let x = 0; x < nx; x++)
          data[z * nx + x] = volume[(z * ny + slice) * nx + x];
    } else {
      imgW = ny; imgH = nz;
      data = new Float32Array(ny * nz);
      for (let z = 0; z < nz; z++)
        for (let y = 0; y < ny; y++)
          data[z * ny + y] = volume[(z * ny + y) * nx + slice];
    }

    let min = Infinity, max = -Infinity;
    for (let i = 0; i < data.length; i++) {
      if (data[i] < min) min = data[i];
      if (data[i] > max) max = data[i];
    }

    canvas.width = imgW;
    canvas.height = imgH;
    const imgData = ctx.createImageData(imgW, imgH);
    const fn = COLORMAPS[colormap] || COLORMAPS.turbo;

    for (let i = 0; i < data.length; i++) {
      const [r, g, b, a] = fn(data[i], min, max);
      imgData.data[i * 4] = r;
      imgData.data[i * 4 + 1] = g;
      imgData.data[i * 4 + 2] = b;
      imgData.data[i * 4 + 3] = a;
    }
    ctx.putImageData(imgData, 0, 0);
  }, [slice, orient, colormap, path]);

  const maxSlice =
    orient === "axial" ? dims[2] - 1 :
    orient === "coronal" ? dims[1] - 1 :
    dims[0] - 1;

  return (
    <div>
      <canvas ref={canvasRef} style={{ width: "100%", imageRendering: "pixelated" }} />
      <div className="slice-controls">
        <input
          type="range"
          min={0}
          max={maxSlice}
          value={slice}
          onChange={(e) => setSlice(parseInt(e.target.value))}
        />
        <span>{slice}/{maxSlice}</span>
        <select value={orient} onChange={(e) => {
          setOrient(e.target.value as any);
          setSlice(Math.floor((e.target.value === "axial" ? dims[2] : e.target.value === "coronal" ? dims[1] : dims[0]) / 2));
        }}>
          <option value="axial">Axial</option>
          <option value="coronal">Coronal</option>
          <option value="sagittal">Sagittal</option>
        </select>
        <select value={colormap} onChange={(e) => setColormap(e.target.value)}>
          <option value="turbo">Turbo</option>
          <option value="gray">Gray</option>
        </select>
      </div>
    </div>
  );
}
