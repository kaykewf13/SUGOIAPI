<?php

namespace App\Controller;

use App\Exceptions\ProviderNotRegisteredException;
use App\Services\MediaService;
use App\Support\ResponseSupport;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

class MediaController
{
    private MediaService $mediaService;

    public function __construct()
    {
        $this->mediaService = new MediaService();
    }

    /**
     * Display a list of episodes.
     *
     * @return string
     *
     * @throws ProviderNotRegisteredException
     */
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