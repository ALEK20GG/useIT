<script lang="ts">
  export let src: string | null = null;
</script>

<div class="pdf-preview">
  {#if src}
    <div class="iframe-wrap">
      <iframe src={src} class="pdf-iframe" title="PDF Preview"></iframe>
    </div>
  {:else}
    <div class="no-pdf">PDF non disponibile</div>
  {/if}
</div>

<style>
  .pdf-preview {
    width: 100%;
    box-sizing: border-box;
  }

  .iframe-wrap {
    width: 100%;
    height: 600px;
    overflow: auto;
    background: #f3f4f6;
    border-radius: 6px;
  }

  .pdf-iframe {
    width: 100%;
    height: 100%;
    border: none;
    display: block;
  }

  .no-pdf {
    padding: 2rem;
    text-align: center;
    color: #6b7280;
  }
</style>
