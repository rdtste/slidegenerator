import { Component } from '@angular/core';
import { Chat } from './features/chat/chat';
import { Editor } from './features/editor/editor';
import { Preview } from './features/preview/preview';
import { ExportPanel } from './features/export-panel/export-panel';
import { Settings } from './features/settings/settings';

@Component({
  selector: 'app-root',
  imports: [Chat, Editor, Preview, ExportPanel, Settings],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {}
