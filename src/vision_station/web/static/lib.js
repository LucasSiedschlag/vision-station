// The three small libraries the screens use, vendored in ./vendor (no build step, no network at the station).
export { h, render, Fragment } from 'preact';
export { useState, useEffect, useRef, useMemo, useCallback, useReducer } from 'preact/hooks';
import { h } from 'preact';
import htm from 'htm';
export const html = htm.bind(h);
