import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  template: `
    <div class="app-container">
      <router-outlet></router-outlet>
    </div>
  `,
  styles: [`
    .app-container {
      min-height: 100vh;
      background: #001219;
    }
  `],
  standalone: true,
  imports: [RouterOutlet]
})
export class AppComponent {
  title = 'Beehive Multi-Agent System';
}
