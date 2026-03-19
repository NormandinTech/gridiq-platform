<!DOCTYPE html>
<html lang="en" class="">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="GridIQ — AI-driven grid intelligence platform for electric utilities" />
    <title>GridIQ Platform</title>

    <!-- Preload fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />

    <style>
      /* Prevent flash of unstyled content */
      html { background: #f8fafc; }
      html.dark { background: #0f172a; }

      /* Loading spinner shown before React mounts */
      #root:empty::after {
        content: '';
        display: block;
        width: 24px;
        height: 24px;
        border: 2px solid #e2e8f0;
        border-top-color: #3b82f6;
        border-radius: 50%;
        animation: spin 0.7s linear infinite;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
      }
      @keyframes spin { to { transform: translate(-50%, -50%) rotate(360deg); } }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
