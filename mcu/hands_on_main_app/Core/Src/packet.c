/*
 * packet.c
 */

#include "aes_ref.h"
#include "config.h"
#include "packet.h"
#include "main.h"
#include "utils.h"
#include <string.h>
#include <stdlib.h>
#include "aes.h"

#ifndef AES
#define AES
#endif

#include "stm32l4xx_hal_cryp.h"
#include "stm32l4xx_hal_cryp_ex.h"

// Fonction de calcul du CBC-MAC en utilisant l'accélérateur matériel AES
void tag_cbc_mac_hardware(uint8_t *tag, const uint8_t *msg, size_t msg_len) {
    // Vérification de l'entrée
    if (tag == NULL || msg == NULL || msg_len == 0) {
        Error_Handler();
        return;
    }

    // Calcul du nombre de blocs de 16 octets (AES block size)
    size_t num_blocks = (msg_len + 15) / 16;
    size_t total_size = num_blocks * 16;

    // Allocation d'un buffer temporaire sur la pile (moins risqué que malloc)
    uint8_t tmp_out[total_size];

    // Chiffrement en mode CBC avec l'accélérateur matériel
    if (HAL_CRYP_AESCBC_Encrypt(&hcryp, (uint8_t *)msg, msg_len, tmp_out, 1000) != HAL_OK) {
        Error_Handler();
        return;
    }

    // Copie du dernier bloc pour obtenir le tag CBC-MAC
    memcpy(tag, tmp_out + ((num_blocks - 1) * 16), 16);
}

// Fonction pour créer un paquet
int make_packet(uint8_t *packet, size_t payload_len, uint8_t sender_id, uint32_t serial) {
    if (packet == NULL || payload_len == 0) {
        return -1; // Retourne une erreur si les paramètres sont invalides
    }

    size_t packet_len = payload_len + PACKET_HEADER_LENGTH + PACKET_TAG_LENGTH;

    // Initialisation de l'entête du paquet
    memset(packet, 0, PACKET_HEADER_LENGTH);
    memset(packet + payload_len + PACKET_HEADER_LENGTH, 0, PACKET_TAG_LENGTH);

    // Remplissage de l'en-tête
    packet[0] = 0x00; // Champ réservé
    packet[1] = sender_id; // ID de l'émetteur
    packet[2] = (payload_len >> 8) & 0xFF;
    packet[3] = payload_len & 0xFF;
    packet[4] = (serial >> 24) & 0xFF;
    packet[5] = (serial >> 16) & 0xFF;
    packet[6] = (serial >> 8) & 0xFF;
    packet[7] = serial & 0xFF;

    // Calcul et ajout du tag CBC-MAC
    tag_cbc_mac_hardware(packet + payload_len + PACKET_HEADER_LENGTH, packet, payload_len + PACKET_HEADER_LENGTH);

    return packet_len;
}
