<?php

namespace App\Controller;

use App\Services\MediaService;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

class MediaController
{
    private MediaService $mediaService;

    public function __construct()
    {
        $this->mediaService = new MediaService();
    }

    #[Route('/', name: 'home', methods: ['GET'])]
    public function home(): JsonResponse
    {
        return new JsonResponse([
            'name' => 'SUGOIAPI',
            'status' => 'online',
            'message' => 'API em funcionamento',
            'endpoints' => [
                '/episode/{slug}/{season}/{episodeNumber}'
            ]
        ]);
    }

    #[Route('/episode/{slug}/{season}/{episodeNumber}', name: 'episodes', methods: ['GET'])]
    public function episodes(string $slug, int $season, int $episodeNumber): JsonResponse
    {
        return new JsonResponse(
            $this->mediaService->searchEpisode($episodeNumber, $season, $slug)
        );
    }
}