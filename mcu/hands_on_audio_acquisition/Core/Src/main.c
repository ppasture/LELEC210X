#include "main.h"
#include "adc.h"
#include "dma.h"
#include "usart.h"
#include "tim.h"
#include "gpio.h"

#include <stdio.h>
#include "retarget.h"

#define ADC_BUF_SIZE 50000
#define HALF_BUF_SIZE (ADC_BUF_SIZE / 2)

volatile uint16_t ADCBuffer[ADC_BUF_SIZE];
volatile uint8_t recording = 0;

void SystemClock_Config(void);
void send_buffer_binary(uint16_t *buffer);
uint32_t get_signal_power(uint16_t *buffer, size_t len);

// Envoie les données du buffer en binaire pur sur l'UART
void send_buffer_binary(uint16_t *buffer) {
    HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_SET);  // LED ON
    HAL_UART_Transmit(&hlpuart1, (uint8_t *)buffer, HALF_BUF_SIZE * sizeof(uint16_t), HAL_MAX_DELAY);
    HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET); // LED OFF
}

// Calcul de la puissance du signal, si besoin
uint32_t get_signal_power(uint16_t *buffer, size_t len) {
    uint64_t sum = 0, sum2 = 0;
    for (size_t i = 0; i < len; i++) {
        sum += buffer[i];
        sum2 += (uint64_t)buffer[i] * buffer[i];
    }
    return (uint32_t)(sum2 / len - (sum * sum) / len / len);
}

// Callback sur bouton pour démarrer/arrêter l’enregistrement
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin) {
    if (GPIO_Pin == B1_Pin) {
        if (!recording) {
            recording = 1;
            HAL_TIM_Base_Start(&htim3);
            HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ADCBuffer, ADC_BUF_SIZE);
            printf("Recording started...\r\n");
        } else {
            recording = 0;
            HAL_ADC_Stop_DMA(&hadc1);
            HAL_TIM_Base_Stop(&htim3);
            printf("Recording stopped.\r\n");
        }
    }
}

// Callback DMA : 1re moitié du buffer remplie
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc) {
    send_buffer_binary((uint16_t *)ADCBuffer);
}

// Callback DMA : 2e moitié du buffer remplie
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc) {
    send_buffer_binary(&ADCBuffer[HALF_BUF_SIZE]);
}

int main(void) {
    HAL_Init();
    SystemClock_Config();

    MX_GPIO_Init();
    MX_DMA_Init();
    MX_LPUART1_UART_Init();
    MX_ADC1_Init();
    MX_TIM3_Init();

    RetargetInit(&hlpuart1);
    printf("Ready. Press the button to start/stop recording.\r\n");

    while (1) {
        __WFI();  // Attente d'interruptions
    }
}

void SystemClock_Config(void) {
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK) {
        Error_Handler();
    }

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
    RCC_OscInitStruct.MSIState = RCC_MSI_ON;
    RCC_OscInitStruct.MSICalibrationValue = 0;
    RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_10;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;

    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                                |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_MSI;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK) {
        Error_Handler();
    }
}

void Error_Handler(void) {
    __disable_irq();
    while (1) {}
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
    // Optionnel : afficher les erreurs
}
#endif
